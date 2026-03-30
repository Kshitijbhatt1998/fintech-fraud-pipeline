# Backend Structure Documentation

> This document defines the complete data model, module architecture, DuckDB schema, dbt model logic, and Python module responsibilities for the fintech fraud detection pipeline.

---

## 1. Architecture Overview

```
src/
├── ingest_data.py     # Stage 1: Raw ingestion + cleaning
└── train.py           # Stage 3: Model training + evaluation

dbt_project/
├── models/
│   ├── staging/       # Stage 2a: Silver layer (views)
│   │   ├── stg_transactions.sql
│   │   └── stg_identity.sql
│   └── marts/         # Stage 2b: Gold layer (tables)
│       ├── fraud_features.sql
│       └── fraud_summary.sql
└── tests/
    └── schema.yml     # 12 data quality assertions

data/
├── raw/               # Source files (not committed)
│   ├── train_transaction.csv
│   └── train_identity.csv
└── fraud.duckdb       # Single-file database (not committed)

models/
└── xgb_fraud_v1.pkl   # Trained model artifact
```

---

## 2. DuckDB Schema

### Table: `raw_transactions`
Source: `data/raw/train_transaction.csv`
Rows: 590,540

| Column | Type | Notes |
|--------|------|-------|
| TransactionID | INTEGER | Primary key |
| TransactionDT | INTEGER | Seconds offset from epoch anchor |
| TransactionAmt | DOUBLE | Transaction amount in USD |
| ProductCD | VARCHAR | W / H / C / S / R |
| isFraud | INTEGER | 0 or 1 — label |
| card1–card6 | MIXED | Card metadata |
| addr1, addr2 | DOUBLE | Billing/shipping zip codes |
| dist1, dist2 | DOUBLE | Distance features |
| P_emaildomain | VARCHAR | Purchaser email domain |
| R_emaildomain | VARCHAR | Recipient email domain |
| C1–C14 | DOUBLE | Counting/behavioral features |
| D1–D15 | DOUBLE | Time-delta features (days since event) |
| M1–M9 | VARCHAR | Match flag strings ('T'/'F'/'M0'/'M1'/'M2') |
| V1–V339 | DOUBLE | Vesta engineered features (many >90% null) |

---

### Table: `raw_identity`
Source: `data/raw/train_identity.csv`
Rows: 144,233

| Column | Type | Notes |
|--------|------|-------|
| TransactionID | INTEGER | Foreign key → raw_transactions |
| id_01–id_38 | MIXED | Device / browser identity features |
| DeviceType | VARCHAR | 'mobile' or 'desktop' |
| DeviceInfo | VARCHAR | Device model string |

---

### Table: `clean_transactions`
Built by: `src/ingest_data.py`
Rows: 590,540 (same as raw — no row-level filtering)

**Columns added vs raw:**
| Column | Type | Logic |
|--------|------|-------|
| transaction_ts | TIMESTAMP | `epoch_ms((TransactionDT + 1511993200) * 1000)` |
| hour_of_day | INTEGER | `hour(transaction_ts)` |
| day_of_week | INTEGER | `dayofweek(transaction_ts)` |
| log_amt | DOUBLE | `ln(TransactionAmt + 1)` |
| has_identity | INTEGER | 1 if TransactionID in raw_identity, else 0 |
| M1_enc–M9_enc | INTEGER | 'T'→1, 'F'→0, 'M0'→0, 'M1'→1, 'M2'→2, NULL→NULL |

**Columns dropped vs raw:**
- All columns with >90% null rate that are NOT in MANDATORY_COLS set
- Typically: most V-features (V1–V339) are dropped
- Mandatory columns always preserved: TransactionID, TransactionDT, TransactionAmt, ProductCD, isFraud, card1–6, addr1–2, dist1–2, P_emaildomain, R_emaildomain, C1–C14, D1–D15

---

### Table: `clean_identity`
Built by: `src/ingest_data.py`
Rows: 144,233 (identical to raw_identity — pass-through)

---

### View: `stg_transactions` (dbt staging)
Built by: `dbt_project/models/staging/stg_transactions.sql`
Source: `clean_transactions`

**Column renames (CamelCase → snake_case):**
| Source Column | Renamed To |
|---------------|-----------|
| TransactionID | transaction_id |
| TransactionDT | transaction_dt |
| TransactionAmt | transaction_amt |
| ProductCD | product_cd |
| isFraud | is_fraud |
| P_emaildomain | purchaser_email_domain |
| R_emaildomain | recipient_email_domain |

All other columns passed through unchanged.

---

### View: `stg_identity` (dbt staging)
Built by: `dbt_project/models/staging/stg_identity.sql`
Source: `clean_identity`

| Column | Renamed To |
|--------|-----------|
| TransactionID | transaction_id |
| DeviceType | device_type |
| id_01–id_38 | id_01–id_38 (unchanged) |

---

### Table: `fraud_features` (dbt mart — Gold)
Built by: `dbt_project/models/marts/fraud_features.sql`
Rows: 590,540
Features: 58 columns + label

**CTEs used:**
```sql
card_stats AS (
    SELECT card1,
           COUNT(*) AS card1_txn_count,
           AVG(transaction_amt) AS card1_avg_amt,
           SUM(is_fraud) AS card1_fraud_count,
           AVG(CAST(is_fraud AS DOUBLE)) AS card1_fraud_rate
    FROM stg_transactions
    GROUP BY card1
)

email_stats AS (
    SELECT purchaser_email_domain,
           COUNT(*) AS email_txn_count,
           AVG(CAST(is_fraud AS DOUBLE)) AS email_fraud_rate
    FROM stg_transactions
    WHERE purchaser_email_domain IS NOT NULL
    GROUP BY purchaser_email_domain
)
```

**Join logic:**
```sql
FROM stg_transactions t
LEFT JOIN stg_identity i ON t.transaction_id = i.transaction_id
LEFT JOIN card_stats cs ON t.card1 = cs.card1
LEFT JOIN email_stats es ON t.purchaser_email_domain = es.purchaser_email_domain
```

**Full column list:**

| Column | Source | Type |
|--------|--------|------|
| transaction_id | stg_transactions | INTEGER |
| transaction_dt | stg_transactions | INTEGER |
| transaction_ts | stg_transactions | TIMESTAMP |
| transaction_amt | stg_transactions | DOUBLE |
| log_amt | stg_transactions | DOUBLE |
| hour_of_day | stg_transactions | INTEGER |
| day_of_week | stg_transactions | INTEGER |
| product_cd | stg_transactions | VARCHAR |
| has_identity | stg_transactions | INTEGER |
| is_fraud | stg_transactions | INTEGER |
| card1–card6 | stg_transactions | MIXED |
| addr1, addr2 | stg_transactions | DOUBLE |
| dist1, dist2 | stg_transactions | DOUBLE |
| purchaser_email_domain | stg_transactions | VARCHAR |
| recipient_email_domain | stg_transactions | VARCHAR |
| C1–C14 | stg_transactions | DOUBLE |
| D1, D2, D3, D4, D5, D10, D11, D15 | stg_transactions | DOUBLE |
| M1_enc–M9_enc | stg_transactions | INTEGER |
| id_01–id_20 | stg_identity | DOUBLE |
| device_type | stg_identity | VARCHAR |
| card1_txn_count | card_stats CTE | BIGINT |
| card1_avg_amt | card_stats CTE | DOUBLE |
| card1_historical_fraud_rate | card_stats CTE | DOUBLE |
| email_txn_count | email_stats CTE | BIGINT |
| email_historical_fraud_rate | email_stats CTE | DOUBLE |
| is_high_risk_product | Computed | INTEGER |
| amt_vs_card_avg_ratio | Computed | DOUBLE |

**Computed column logic:**
```sql
CASE WHEN product_cd = 'W' THEN 1 ELSE 0 END AS is_high_risk_product,

CASE
    WHEN card1_avg_amt > 0 THEN transaction_amt / card1_avg_amt
    ELSE NULL
END AS amt_vs_card_avg_ratio
```

---

### Table: `fraud_summary` (dbt mart — Gold)
Built by: `dbt_project/models/marts/fraud_summary.sql`

**Schema:**
| Column | Type | Description |
|--------|------|-------------|
| grain | VARCHAR | 'daily' / 'product' / 'card_type' / 'email_domain' / 'hour_of_day' |
| dim_value | VARCHAR | Value of the dimension (date string, product code, etc.) |
| txn_count | BIGINT | Total transactions in segment |
| fraud_count | BIGINT | Fraud transactions in segment |
| fraud_rate_pct | DOUBLE | `fraud_count / txn_count * 100` |
| total_amt | DOUBLE | Total transaction amount |
| fraud_amt | DOUBLE | Total fraud transaction amount |

**Aggregation dimensions:**
- `daily` — grouped by `CAST(transaction_ts AS DATE)`
- `product` — grouped by `product_cd`
- `card_type` — grouped by `card6`
- `email_domain` — grouped by `purchaser_email_domain`
- `hour_of_day` — grouped by `hour_of_day`

---

## 3. Python Module Responsibilities

### `src/ingest_data.py`

**Responsibility**: Stages 1 and 2 — raw ingestion and cleaning

**Functions:**
```python
def main():
    """
    Entry point. Orchestrates:
    1. DuckDB connection + database reset
    2. CSV ingestion → raw_transactions, raw_identity
    3. Null analysis → drop high-null columns
    4. Feature engineering → clean_transactions
    5. Identity passthrough → clean_identity
    """
```

**Key constants:**
```python
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "fraud.duckdb"
RAW_PATH = BASE_DIR / "data" / "raw"
BASE_DT_EPOCH = int(pd.Timestamp('2017-11-30').timestamp())  # = 1511993200
THRESHOLD = 90.0  # % null threshold for column drop
MANDATORY_COLS = {
    'TransactionID', 'TransactionDT', 'TransactionAmt', 'ProductCD', 'isFraud',
    'card1', 'card2', 'card3', 'card4', 'card5', 'card6',
    'addr1', 'addr2', 'dist1', 'dist2',
    'P_emaildomain', 'R_emaildomain',
    'C1'–'C14', 'D1'–'D15'
}
```

**Null analysis approach:**
```sql
SELECT
    ROUND(COUNT(*) FILTER (WHERE col IS NULL) * 100.0 / COUNT(*), 2) AS col
    -- repeated for every column
FROM raw_transactions
```
Executed as a single SQL query for performance — avoids Python loop over rows.

---

### `src/train.py`

**Responsibility**: Stage 3 — model training, evaluation, and logging

**Functions:**
```python
def load_features(db_path: Path) -> pd.DataFrame:
    """Load fraud_features from DuckDB sorted by transaction_dt ASC."""

def encode_categoricals(df, cat_cols) -> tuple[pd.DataFrame, dict]:
    """Label-encode categorical columns. Fills NaN with 'MISSING' before encoding."""

def build_feature_matrix(df) -> tuple[pd.DataFrame, pd.Series]:
    """Filter to available features, encode categoricals, return X and y."""

def train(X, y) -> tuple[XGBClassifier, float, float, list]:
    """
    Train XGBoost with 5-fold TimeSeriesSplit.
    Returns: model, cv_mean_auc, cv_mean_ap, fold_auc_scores
    scale_pos_weight = (1 - fraud_rate) / fraud_rate  ≈ 28 for 3.5% fraud
    """

def evaluate_holdout(model, X, y) -> tuple[float, float, array, Series]:
    """Evaluate on last 20% of data (time-based holdout, not random split)."""

def main():
    """MLflow run orchestration: load → build → train → evaluate → log → save."""
```

**Feature configuration:**
```python
NUMERIC_FEATURES = [
    'transaction_amt', 'log_amt', 'hour_of_day', 'day_of_week', 'has_identity',
    'card1', 'card2', 'card3', 'card5', 'addr1', 'addr2', 'dist1', 'dist2',
    'C1'–'C14', 'D1'–'D5', 'D10', 'D11', 'D15',
    'M1_enc'–'M9_enc',
    'id_01', 'id_02', 'id_03', 'id_05', 'id_06', 'id_09', 'id_11',
    'id_13', 'id_17', 'id_19', 'id_20',
    'card1_txn_count', 'card1_avg_amt', 'card1_historical_fraud_rate',
    'email_txn_count', 'email_historical_fraud_rate',
    'is_high_risk_product', 'amt_vs_card_avg_ratio',
]
CATEGORICAL_FEATURES = ['product_cd', 'card4', 'card6', 'device_type']
TARGET = 'is_fraud'
```

**XGBoost hyperparameters:**
```python
model = xgb.XGBClassifier(
    n_estimators=500,
    learning_rate=0.05,
    max_depth=6,
    min_child_weight=5,
    subsample=0.8,
    colsample_bytree=0.8,
    scale_pos_weight=~28,   # computed dynamically from fraud rate
    eval_metric='auc',
    random_state=42,
    n_jobs=-1,
    early_stopping_rounds=30,
)
```

---

### `src/dashboard.py`

**Responsibility**: Stage 4 — interactive results exploration

**Key functions:**
```python
@st.cache_data(ttl=300)
def load_summary() -> pd.DataFrame:
    """Load fraud_summary from DuckDB or return demo synthetic data."""

@st.cache_data(ttl=300)
def load_sample(n=50_000) -> pd.DataFrame:
    """Load sample of fraud_features for transaction explorer."""

@st.cache_data(ttl=600)
def load_model_data() -> tuple | None:
    """Load model artifact + holdout data for model performance tab."""
```

---

## 4. dbt Data Quality Tests

All tests defined in `dbt_project/tests/schema.yml`:

| Test | Model | Column | Assertion |
|------|-------|--------|-----------|
| unique | stg_transactions | transaction_id | No duplicates |
| not_null | stg_transactions | transaction_id | Required |
| not_null | stg_transactions | is_fraud | Label always present |
| not_null | stg_transactions | transaction_amt | Amount always present |
| not_null | stg_transactions | product_cd | Product always present |
| accepted_values | stg_transactions | is_fraud | Values in {0, 1} |
| accepted_values | stg_transactions | product_cd | Values in {W, H, C, S, R} |
| not_null | stg_identity | transaction_id | Required |
| unique | fraud_features | transaction_id | No duplicates in mart |
| not_null | fraud_features | transaction_id | Required |
| not_null | fraud_features | is_fraud | Label in mart |
| not_null | fraud_summary | grain | Grain always labelled |
| accepted_values | fraud_summary | grain | Values in {daily, product, card_type, email_domain, hour_of_day} |

---

## 5. MLflow Experiment Structure

**Experiment name**: `fraud_detection`
**Run name**: `xgb_baseline`

**Logged params:**
```
n_estimators: 500
learning_rate: 0.05
max_depth: 6
scale_pos_weight: 28.xx
n_features: 58
```

**Logged metrics:**
```
cv_mean_auc: 0.9791
cv_mean_ap: [value]
holdout_auc: 0.9791
holdout_ap: [value]
fold_1_auc: [value]
fold_2_auc: [value]
fold_3_auc: [value]
fold_4_auc: [value]
fold_5_auc: [value]
```

**Artifact path**: `mlruns/1/{run_id}/artifacts/xgb_fraud_v1.pkl`

---

## 6. File Structure (Complete)

```
fintech-fraud-pipeline/
├── src/
│   ├── ingest_data.py
│   ├── train.py
│   └── dashboard.py
├── dbt_project/
│   ├── models/
│   │   ├── staging/
│   │   │   ├── stg_transactions.sql
│   │   │   ├── stg_identity.sql
│   │   │   └── sources.yml
│   │   └── marts/
│   │       ├── fraud_features.sql
│   │       └── fraud_summary.sql
│   ├── tests/
│   │   └── schema.yml
│   ├── dbt_project.yml
│   └── profiles.yml
├── data/
│   └── raw/                  # Not committed — Kaggle download required
├── models/
│   └── xgb_fraud_v1.pkl      # Not committed — generated by train.py
├── notebooks/
│   ├── 01_eda.ipynb
│   ├── 02_data_pipeline.ipynb
│   └── 03_model_eval.ipynb
├── mlruns/                   # Not committed (binary artifacts)
├── README.md
├── DATA_PIPELINE.md
├── TECH_STACK.md
├── FRONTEND_GUIDELINES.md
├── BACKEND_STRUCTURE.md
├── IMPLEMENTATION_PLAN.md
├── PRD.md
├── APP_FLOW.md
└── requirements.txt
```

---

## 7. .gitignore Rules

```gitignore
# Data files (too large + Kaggle TOS)
data/raw/
data/*.duckdb
data/*.parquet

# Model artifacts (regenerated by train.py)
models/*.pkl

# MLflow binary artifacts
mlruns/*/artifacts/

# Python environment
.venv/
__pycache__/
*.pyc

# dbt artifacts
dbt_project/target/
dbt_project/dbt_packages/
```
