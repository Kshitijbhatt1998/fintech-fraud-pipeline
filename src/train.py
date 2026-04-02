"""
XGBoost Fraud Detection Model — Training Script

Usage:
    python src/train.py

Reads from: data/fraud.duckdb (fraud_features table built by dbt)
Outputs:    models/xgb_fraud_v1.pkl
            MLflow experiment: fraud_detection
"""

import duckdb
import numpy as np
import pandas as pd
import pickle
import logging
from pathlib import Path

import mlflow
import mlflow.xgboost
import xgboost as xgb
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.metrics import (
    roc_auc_score, average_precision_score,
    classification_report, confusion_matrix
)
from sklearn.preprocessing import LabelEncoder

from src.monitoring import setup_monitoring, capture_exception, capture_message

log = setup_monitoring('train')

# ─── Paths ────────────────────────────────────────────────────────────────────
ROOT       = Path(__file__).resolve().parent.parent
DB_PATH    = ROOT / 'data' / 'fraud.duckdb'
MODEL_DIR  = ROOT / 'models'
MODEL_PATH = MODEL_DIR / 'xgb_fraud_v1.pkl'

MODEL_DIR.mkdir(exist_ok=True)

# ─── Feature config ───────────────────────────────────────────────────────────
NUMERIC_FEATURES = [
    'transaction_amt', 'log_amt', 'hour_of_day', 'day_of_week',
    'has_identity',
    'card1', 'card2', 'card3', 'card5',
    'addr1', 'addr2', 'dist1', 'dist2',
    'C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'C8', 'C9', 'C10', 'C11', 'C12', 'C13', 'C14',
    'D1', 'D2', 'D3', 'D4', 'D5', 'D10', 'D11', 'D15',
    'M1_enc', 'M2_enc', 'M3_enc', 'M4_enc', 'M5_enc', 'M6_enc', 'M7_enc', 'M8_enc', 'M9_enc',
    'id_01', 'id_02', 'id_03', 'id_05', 'id_06', 'id_09', 'id_11',
    'id_13', 'id_17', 'id_19', 'id_20',
    'card1_txn_count', 'card1_avg_amt', 'card1_historical_fraud_rate',
    'email_txn_count', 'email_historical_fraud_rate',
    'is_high_risk_product', 'amt_vs_card_avg_ratio',
]

CATEGORICAL_FEATURES = ['product_cd', 'card4', 'card6', 'device_type']

TARGET = 'is_fraud'


def load_features(db_path: Path) -> pd.DataFrame:
    """Load fraud_features table from DuckDB, sorted by transaction time."""
    log.info(f'Loading features from {db_path}')
    con = duckdb.connect(str(db_path), read_only=True)
    df = con.execute("""
        SELECT * FROM fraud_features
        ORDER BY transaction_dt ASC
    """).df()
    con.close()
    log.info(f'Loaded {len(df):,} rows x {df.shape[1]} cols')
    return df


def encode_categoricals(df: pd.DataFrame, cat_cols: list) -> tuple[pd.DataFrame, dict]:
    """Label-encode categorical columns. Returns df and encoder map."""
    encoders = {}
    for col in cat_cols:
        if col not in df.columns:
            continue
        le = LabelEncoder()
        df[col] = le.fit_transform(df[col].fillna('MISSING').astype(str))
        encoders[col] = le
    return df, encoders


def build_feature_matrix(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Return X (features) and y (target)."""
    available_numeric = [c for c in NUMERIC_FEATURES if c in df.columns]
    available_cat     = [c for c in CATEGORICAL_FEATURES if c in df.columns]

    df, _ = encode_categoricals(df, available_cat)

    feature_cols = available_numeric + available_cat
    X = df[feature_cols].copy()
    y = df[TARGET].copy()

    log.info(f'Feature matrix: {X.shape[0]:,} rows x {X.shape[1]} features')
    log.info(f'Fraud rate: {y.mean():.2%}')
    return X, y


def train(X: pd.DataFrame, y: pd.Series) -> xgb.XGBClassifier:
    """Train XGBoost with time-series cross-validation."""
    fraud_rate = y.mean()
    scale_pos_weight = (1 - fraud_rate) / fraud_rate  # ~28 for 3.5% fraud

    model = xgb.XGBClassifier(
        n_estimators=500,
        learning_rate=0.05,
        max_depth=6,
        min_child_weight=5,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=scale_pos_weight,
        eval_metric='auc',
        random_state=42,
        n_jobs=-1,
        early_stopping_rounds=30,
    )

    # Time-series split — never shuffle fraud data
    tscv = TimeSeriesSplit(n_splits=5)

    log.info('Starting 5-fold time-series cross-validation...')
    auc_scores = []
    ap_scores  = []

    for fold, (train_idx, val_idx) in enumerate(tscv.split(X), 1):
        X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=False,
        )

        proba = model.predict_proba(X_val)[:, 1]
        auc = roc_auc_score(y_val, proba)
        ap  = average_precision_score(y_val, proba)
        auc_scores.append(auc)
        ap_scores.append(ap)
        log.info(f'  Fold {fold}: AUC={auc:.4f}  AP={ap:.4f}')

    mean_auc = np.mean(auc_scores)
    mean_ap  = np.mean(ap_scores)
    log.info(f'CV Mean AUC: {mean_auc:.4f} (+/- {np.std(auc_scores):.4f})')
    log.info(f'CV Mean AP:  {mean_ap:.4f} (+/- {np.std(ap_scores):.4f})')

    # Final fit on all data
    log.info('Fitting final model on full training set...')
    model.set_params(early_stopping_rounds=None)
    model.fit(X, y, verbose=False)

    return model, mean_auc, mean_ap, auc_scores


def evaluate_holdout(model, X, y):
    """Evaluate on last 20% of data (time-based holdout)."""
    n = len(X)
    split = int(n * 0.8)
    X_hold, y_hold = X.iloc[split:], y.iloc[split:]

    proba = model.predict_proba(X_hold)[:, 1]
    preds = (proba >= 0.5).astype(int)

    auc = roc_auc_score(y_hold, proba)
    ap  = average_precision_score(y_hold, proba)

    log.info(f'Holdout AUC: {auc:.4f}  AP: {ap:.4f}')
    log.info('\nClassification Report (threshold=0.5):\n' +
             classification_report(y_hold, preds, target_names=['Legit', 'Fraud']))

    return auc, ap, proba, y_hold


def main():
    mlflow.set_experiment('fraud_detection')

    with mlflow.start_run(run_name='xgb_baseline'):
        df = load_features(DB_PATH)
        X, y = build_feature_matrix(df)

        model, cv_auc, cv_ap, fold_aucs = train(X, y)
        holdout_auc, holdout_ap, proba, y_hold = evaluate_holdout(model, X, y)

        # Feature importance
        fi = pd.Series(model.feature_importances_, index=X.columns)
        fi = fi.sort_values(ascending=False)
        log.info('\nTop 15 feature importances:')
        log.info(fi.head(15).to_string())

        # MLflow logging
        mlflow.log_params({
            'n_estimators': model.n_estimators,
            'learning_rate': model.learning_rate,
            'max_depth': model.max_depth,
            'scale_pos_weight': round(model.scale_pos_weight, 2),
            'n_features': X.shape[1],
        })
        mlflow.log_metrics({
            'cv_mean_auc':  round(cv_auc, 4),
            'cv_mean_ap':   round(cv_ap, 4),
            'holdout_auc':  round(holdout_auc, 4),
            'holdout_ap':   round(holdout_ap, 4),
        })
        for i, auc in enumerate(fold_aucs, 1):
            mlflow.log_metric(f'fold_{i}_auc', round(auc, 4))

        mlflow.xgboost.log_model(model, name='xgb_model')

        # Save model artifact
        with open(MODEL_PATH, 'wb') as f:
            pickle.dump({'model': model, 'feature_cols': X.columns.tolist()}, f)
        mlflow.log_artifact(str(MODEL_PATH))

        log.info(f'Model saved to {MODEL_PATH}')
        log.info(f'MLflow run ID: {mlflow.active_run().info.run_id}')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        capture_exception(exc, {'script': 'train'})
        capture_message(f'Training failed: {exc}', level='error')
        raise
