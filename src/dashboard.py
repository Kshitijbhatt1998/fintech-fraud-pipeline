"""
Fraud Detection Dashboard — Streamlit App

Usage:
    streamlit run src/dashboard.py

Requires: data/fraud.duckdb with fraud_summary and fraud_features tables
          models/xgb_fraud_v1.pkl (optional — for model performance tab)
"""

import pickle
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sklearn.metrics import roc_curve, auc, confusion_matrix

# ─── Config ───────────────────────────────────────────────────────────────────
ROOT       = Path(__file__).resolve().parent.parent
DB_PATH    = ROOT / 'data' / 'fraud.duckdb'
MODEL_PATH = ROOT / 'models' / 'xgb_fraud_v1.pkl'

st.set_page_config(
    page_title='Fraud Detection Pipeline',
    page_icon='🔍',
    layout='wide',
    initial_sidebar_state='expanded',
)

# ─── Data Loading ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_summary():
    con = duckdb.connect(str(DB_PATH), read_only=True)
    df = con.execute('SELECT * FROM fraud_summary').df()
    con.close()
    return df


@st.cache_data(ttl=300)
def load_sample(n=50_000):
    """Load a sample of fraud_features for transaction explorer."""
    con = duckdb.connect(str(DB_PATH), read_only=True)
    df = con.execute(f"""
        SELECT
            transaction_id, transaction_ts, transaction_amt,
            product_cd, card4, card6, purchaser_email_domain,
            is_fraud, hour_of_day, day_of_week, has_identity
        FROM fraud_features
        ORDER BY transaction_dt DESC
        LIMIT {n}
    """).df()
    con.close()
    return df


@st.cache_data(ttl=600)
def load_model_data():
    """Load model + holdout predictions for performance tab."""
    if not MODEL_PATH.exists():
        return None
    with open(MODEL_PATH, 'rb') as f:
        artifact = pickle.load(f)
    con = duckdb.connect(str(DB_PATH), read_only=True)
    feat_cols = artifact['feature_cols']
    available = con.execute('DESCRIBE fraud_features').df()['column_name'].tolist()
    cols_to_load = [c for c in feat_cols if c in available] + ['is_fraud', 'transaction_dt']
    df = con.execute(f"""
        SELECT {', '.join(cols_to_load)}
        FROM fraud_features
        ORDER BY transaction_dt ASC
    """).df()
    con.close()
    return artifact, df


# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title('🔍 Fraud Pipeline')
    st.caption('IEEE-CIS Dataset • XGBoost Model')
    st.divider()
    st.markdown('**Navigate:**')
    tab_selection = st.radio('', ['Overview', 'Risk Breakdown', 'Model Performance', 'Transaction Explorer'],
                             label_visibility='collapsed')

# ─── Load data ────────────────────────────────────────────────────────────────
try:
    summary = load_summary()
    sample  = load_sample()
    data_ok = True
except Exception as e:
    st.error(f'Could not connect to fraud.duckdb: {e}')
    st.info('Run notebook 02_data_pipeline.ipynb and `dbt run` first.')
    st.stop()

# Pre-extract sub-dataframes
daily_df    = summary[summary['grain'] == 'daily'].copy()
daily_df['dim_value'] = pd.to_datetime(daily_df['dim_value'])
daily_df = daily_df.sort_values('dim_value')

product_df  = summary[summary['grain'] == 'product']
card_df     = summary[summary['grain'] == 'card_type']
email_df    = summary[summary['grain'] == 'email_domain']
hour_df     = summary[summary['grain'] == 'hour_of_day'].copy()
hour_df['dim_value'] = hour_df['dim_value'].astype(int)
hour_df = hour_df.sort_values('dim_value')

# Overall KPIs
total_txns    = int(daily_df['txn_count'].sum())
total_fraud   = int(daily_df['fraud_count'].sum())
fraud_rate    = total_fraud / total_txns if total_txns else 0
total_fraud_amt = daily_df['fraud_amt'].sum()
total_amt     = daily_df['total_amt'].sum()


# ─── Tab: Overview ────────────────────────────────────────────────────────────
if tab_selection == 'Overview':
    st.title('Fraud Detection — Overview')

    col1, col2, col3, col4 = st.columns(4)
    col1.metric('Total Transactions', f'{total_txns:,}')
    col2.metric('Fraud Rate', f'{fraud_rate:.2%}')
    col3.metric('Fraud Transactions', f'{total_fraud:,}')
    col4.metric('Total Fraud Amount', f'${total_fraud_amt:,.0f}')

    st.divider()

    # Daily volume + fraud rate
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=daily_df['dim_value'], y=daily_df['txn_count'],
        name='Total Transactions', marker_color='#4C72B0', opacity=0.7,
        yaxis='y1'
    ))
    fig.add_trace(go.Scatter(
        x=daily_df['dim_value'], y=daily_df['fraud_rate_pct'],
        name='Fraud Rate (%)', mode='lines', line=dict(color='#DD8452', width=2),
        yaxis='y2'
    ))
    fig.update_layout(
        title='Daily Transaction Volume & Fraud Rate',
        yaxis=dict(title='Transactions', showgrid=False),
        yaxis2=dict(title='Fraud Rate (%)', overlaying='y', side='right', showgrid=False),
        legend=dict(orientation='h', y=1.1),
        height=400,
        plot_bgcolor='white',
    )
    st.plotly_chart(fig, use_container_width=True)

    # Daily fraud amount
    fig2 = px.area(
        daily_df, x='dim_value', y='fraud_amt',
        title='Daily Fraud Amount ($)',
        labels={'dim_value': 'Date', 'fraud_amt': 'Fraud Amount ($)'},
        color_discrete_sequence=['#d62728'],
    )
    fig2.update_layout(height=300, plot_bgcolor='white')
    st.plotly_chart(fig2, use_container_width=True)


# ─── Tab: Risk Breakdown ──────────────────────────────────────────────────────
elif tab_selection == 'Risk Breakdown':
    st.title('Risk Breakdown')

    col1, col2 = st.columns(2)

    with col1:
        fig = px.bar(
            product_df.sort_values('fraud_rate_pct', ascending=False),
            x='dim_value', y='fraud_rate_pct',
            title='Fraud Rate by Product Code',
            labels={'dim_value': 'Product', 'fraud_rate_pct': 'Fraud Rate (%)'},
            color='fraud_rate_pct', color_continuous_scale='Reds',
            text='fraud_rate_pct',
        )
        fig.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
        fig.update_layout(height=350, plot_bgcolor='white', showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = px.bar(
            card_df.sort_values('fraud_rate_pct', ascending=False),
            x='dim_value', y='fraud_rate_pct',
            title='Fraud Rate by Card Type',
            labels={'dim_value': 'Card Type', 'fraud_rate_pct': 'Fraud Rate (%)'},
            color='fraud_rate_pct', color_continuous_scale='Oranges',
            text='fraud_rate_pct',
        )
        fig.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
        fig.update_layout(height=350, plot_bgcolor='white', showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    # Email domain heatmap
    email_sorted = email_df.sort_values('fraud_rate_pct', ascending=True).tail(15)
    fig3 = px.bar(
        email_sorted, x='fraud_rate_pct', y='dim_value', orientation='h',
        title='Top 15 Email Domains by Fraud Rate',
        labels={'dim_value': 'Email Domain', 'fraud_rate_pct': 'Fraud Rate (%)'},
        color='fraud_rate_pct', color_continuous_scale='YlOrRd',
    )
    fig3.update_layout(height=450, plot_bgcolor='white')
    st.plotly_chart(fig3, use_container_width=True)

    # Hourly heatmap
    fig4 = px.bar(
        hour_df, x='dim_value', y='fraud_rate_pct',
        title='Fraud Rate by Hour of Day',
        labels={'dim_value': 'Hour', 'fraud_rate_pct': 'Fraud Rate (%)'},
        color='fraud_rate_pct', color_continuous_scale='Blues',
    )
    fig4.update_layout(height=300, plot_bgcolor='white')
    st.plotly_chart(fig4, use_container_width=True)


# ─── Tab: Model Performance ───────────────────────────────────────────────────
elif tab_selection == 'Model Performance':
    st.title('Model Performance')

    result = load_model_data()
    if result is None:
        st.warning('Model not trained yet. Run `python src/train.py` first.')
        st.stop()

    artifact, df = result
    model = artifact['model']
    feat_cols = [c for c in artifact['feature_cols'] if c in df.columns]

    # Holdout: last 20%
    n = len(df)
    split = int(n * 0.8)
    X_hold = df[feat_cols].iloc[split:]
    y_hold = df['is_fraud'].iloc[split:]
    proba  = model.predict_proba(X_hold)[:, 1]
    preds  = (proba >= 0.5).astype(int)

    fpr, tpr, _ = roc_curve(y_hold, proba)
    roc_auc = auc(fpr, tpr)

    col1, col2, col3 = st.columns(3)
    col1.metric('Holdout AUC-ROC', f'{roc_auc:.4f}')
    col2.metric('Fraud Rate (holdout)', f'{y_hold.mean():.2%}')
    col3.metric('Holdout samples', f'{len(y_hold):,}')

    st.divider()

    left, right = st.columns(2)

    with left:
        # ROC curve
        fig_roc = go.Figure()
        fig_roc.add_trace(go.Scatter(x=fpr, y=tpr, mode='lines', name=f'XGBoost (AUC={roc_auc:.3f})',
                                     line=dict(color='#DD8452', width=2)))
        fig_roc.add_trace(go.Scatter(x=[0,1], y=[0,1], mode='lines', name='Random',
                                     line=dict(color='gray', dash='dash')))
        fig_roc.update_layout(title='ROC Curve', xaxis_title='FPR', yaxis_title='TPR',
                               height=400, plot_bgcolor='white')
        st.plotly_chart(fig_roc, use_container_width=True)

    with right:
        # Confusion matrix
        cm = confusion_matrix(y_hold, preds)
        fig_cm = px.imshow(
            cm, text_auto=True,
            labels=dict(x='Predicted', y='Actual', color='Count'),
            x=['Legit', 'Fraud'], y=['Legit', 'Fraud'],
            color_continuous_scale='Blues',
            title='Confusion Matrix (threshold=0.5)',
        )
        fig_cm.update_layout(height=400)
        st.plotly_chart(fig_cm, use_container_width=True)

    # Feature importance
    fi = pd.DataFrame({
        'feature': feat_cols,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False).head(20)

    fig_fi = px.bar(
        fi, x='importance', y='feature', orientation='h',
        title='Top 20 Feature Importances',
        color='importance', color_continuous_scale='Viridis',
    )
    fig_fi.update_layout(height=500, plot_bgcolor='white', yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig_fi, use_container_width=True)


# ─── Tab: Transaction Explorer ────────────────────────────────────────────────
elif tab_selection == 'Transaction Explorer':
    st.title('Transaction Explorer')
    st.caption(f'Showing most recent 50,000 transactions')

    col1, col2, col3 = st.columns(3)
    with col1:
        product_filter = st.multiselect('Product Code', options=sorted(sample['product_cd'].dropna().unique()))
    with col2:
        card_filter = st.multiselect('Card Type', options=sorted(sample['card6'].dropna().unique()))
    with col3:
        fraud_filter = st.selectbox('Show', ['All', 'Fraud only', 'Legitimate only'])

    filtered = sample.copy()
    if product_filter:
        filtered = filtered[filtered['product_cd'].isin(product_filter)]
    if card_filter:
        filtered = filtered[filtered['card6'].isin(card_filter)]
    if fraud_filter == 'Fraud only':
        filtered = filtered[filtered['is_fraud'] == 1]
    elif fraud_filter == 'Legitimate only':
        filtered = filtered[filtered['is_fraud'] == 0]

    st.write(f'{len(filtered):,} transactions match filters')

    display_cols = ['transaction_id', 'transaction_ts', 'transaction_amt',
                    'product_cd', 'card4', 'card6', 'purchaser_email_domain',
                    'hour_of_day', 'has_identity', 'is_fraud']
    st.dataframe(
        filtered[display_cols].rename(columns={'is_fraud': 'FRAUD'}).head(1000),
        use_container_width=True,
        column_config={
            'FRAUD': st.column_config.NumberColumn(format='%d', help='1=Fraud, 0=Legit'),
            'transaction_amt': st.column_config.NumberColumn(format='$%.2f'),
        }
    )
