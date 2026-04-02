"""
Fraud Detection Dashboard — Streamlit App

Production features:
  - @st.fragment island rendering (Streamlit 1.37+): each tab rerenders independently
  - Supabase authentication gate (see src/auth.py)
  - Sentry error tracking (see src/monitoring.py)
  - Session-level rate limiting on expensive operations
  - Graceful error boundaries — no stack traces exposed to users
  - PostHog analytics events on tab navigation and data export

Usage:
    streamlit run src/dashboard.py

Requires: data/fraud.duckdb with fraud_summary and fraud_features tables
          models/xgb_fraud_v1.pkl (optional — for model performance tab)
"""

import logging
import pickle
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sklearn.metrics import roc_curve, auc, confusion_matrix

# ── Monitoring must be initialized before anything else ───────────────────────
from src.monitoring import setup_monitoring, capture_exception
logger = setup_monitoring('dashboard')

# ── Auth ──────────────────────────────────────────────────────────────────────
from src.auth import require_auth, sign_out
from src.rate_limit import check_rate_limit

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

# ── Authenticate before rendering anything ────────────────────────────────────
user = require_auth()

# ─── Demo Banner ─────────────────────────────────────────────────────────────
DEMO_MODE = not DB_PATH.exists()
if DEMO_MODE:
    st.info(
        "**Demo Mode** — showing sample data. "
        "The full pipeline processes 590,540 real transactions with AUC 0.9791. "
        "[View the code on GitHub](https://github.com/Kshitijbhatt1998/fintech-fraud-pipeline)",
        icon="ℹ️"
    )

# ─── Demo Mode Generators ─────────────────────────────────────────────────────
def get_demo_summary():
    np.random.seed(42)
    dates = pd.date_range('2017-12-01', periods=180, freq='D')
    daily_txns = np.random.randint(2800, 6200, 180)
    daily_fraud_rate = np.random.uniform(0.025, 0.065, 180)

    daily = pd.DataFrame({
        'grain': 'daily', 'dim_value': dates.strftime('%Y-%m-%d'),
        'txn_count': daily_txns,
        'fraud_count': (daily_txns * daily_fraud_rate).astype(int),
        'fraud_rate_pct': daily_fraud_rate * 100,
        'total_amt': daily_txns * np.random.uniform(80, 140, 180),
        'fraud_amt': daily_txns * daily_fraud_rate * np.random.uniform(90, 160, 180),
    })
    products = ['W', 'H', 'C', 'S', 'R']
    prod_txns = [280000, 120000, 80000, 50000, 30000]
    prod_rates = [2.5, 3.8, 10.5, 4.2, 5.0]
    product = pd.DataFrame({
        'grain': 'product', 'dim_value': products, 'txn_count': prod_txns,
        'fraud_count': [int(t * r / 100) for t, r in zip(prod_txns, prod_rates)],
        'fraud_rate_pct': prod_rates,
        'total_amt': [t * 100 for t in prod_txns],
        'fraud_amt': [int(t * r / 100 * 110) for t, r in zip(prod_txns, prod_rates)],
    })
    card = pd.DataFrame({
        'grain': 'card_type', 'dim_value': ['debit', 'credit', 'charge card'],
        'txn_count': [350000, 180000, 20000], 'fraud_rate_pct': [2.5, 6.5, 1.2],
        'fraud_count': [1, 1, 1], 'total_amt': [1, 1, 1], 'fraud_amt': [1, 1, 1],
    })
    emails = ['gmail.com', 'outlook.com', 'hotmail.com', 'yahoo.com', 'anonymous.com']
    email = pd.DataFrame({
        'grain': 'email_domain', 'dim_value': emails,
        'fraud_rate_pct': [2.8, 9.5, 12.2, 3.5, 5.1],
        'txn_count': [200000, 50000, 40000, 30000, 20000],
        'fraud_count': [1, 1, 1, 1, 1], 'total_amt': [1]*5, 'fraud_amt': [1]*5,
    })
    hour = pd.DataFrame({
        'grain': 'hour_of_day', 'dim_value': [str(h) for h in range(24)],
        'fraud_rate_pct': [3 + np.sin(h / 24 * 2 * np.pi) + np.random.normal(0, 0.5)
                           for h in range(24)],
        'txn_count': [5000] * 24, 'fraud_count': [1]*24, 'total_amt': [1]*24, 'fraud_amt': [1]*24,
    })
    return pd.concat([daily, product, card, email, hour], ignore_index=True)


def get_demo_sample():
    np.random.seed(123)
    n = 5000
    return pd.DataFrame({
        'transaction_id': range(1000000, 1000000 + n),
        'transaction_ts': pd.date_range('2017-12-01', periods=n, freq='30min'),
        'transaction_amt': np.random.lognormal(4.5, 1.2, n).round(2),
        'product_cd': np.random.choice(['W','H','C','S','R'], n, p=[0.45,0.25,0.15,0.10,0.05]),
        'card4': np.random.choice(['visa','mastercard','american express','discover'], n,
                                   p=[0.55, 0.30, 0.10, 0.05]),
        'card6': np.random.choice(['debit','credit','charge card'], n, p=[0.60,0.35,0.05]),
        'purchaser_email_domain': np.random.choice(
            ['gmail.com','outlook.com','hotmail.com','yahoo.com','icloud.com',
             'anonymous.com','msn.com','aol.com'], n),
        'is_fraud': np.random.choice([0, 1], n, p=[0.965, 0.035]),
        'hour_of_day': np.random.randint(0, 24, n),
        'day_of_week': np.random.randint(0, 7, n),
        'has_identity': np.random.choice([0, 1], n, p=[0.75, 0.25]),
        'transaction_dt': pd.date_range('2017-12-01', periods=n, freq='30min').date,
    })


# ─── Data Loading ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_summary():
    if DEMO_MODE:
        return get_demo_summary()
    con = duckdb.connect(str(DB_PATH), read_only=True)
    df = con.execute('SELECT * FROM fraud_summary').df()
    con.close()
    return df


@st.cache_data(ttl=300)
def load_sample(n: int = 50_000):
    # Sanitize: clamp to safe bounds before SQL interpolation
    n = min(max(1, int(n)), 500_000)
    if DEMO_MODE:
        return get_demo_sample()
    con = duckdb.connect(str(DB_PATH), read_only=True)
    df = con.execute(f"""
        SELECT transaction_id, transaction_ts, transaction_amt,
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
    if DEMO_MODE or not MODEL_PATH.exists():
        return None
    with open(MODEL_PATH, 'rb') as f:
        artifact = pickle.load(f)
    con = duckdb.connect(str(DB_PATH), read_only=True)
    feat_cols = artifact['feature_cols']
    available = con.execute('DESCRIBE fraud_features').df()['column_name'].tolist()
    cols = [c for c in feat_cols if c in available] + ['is_fraud', 'transaction_dt']
    df = con.execute(f"SELECT {', '.join(cols)} FROM fraud_features ORDER BY transaction_dt ASC").df()
    con.close()
    return artifact, df


# ─── Analytics helper ─────────────────────────────────────────────────────────
def _track(event: str, props: dict | None = None) -> None:
    """Fire a PostHog server-side event (no-op if POSTHOG_API_KEY not set)."""
    import os
    key  = os.getenv('POSTHOG_API_KEY')
    host = os.getenv('POSTHOG_HOST', 'https://us.i.posthog.com')
    if not key:
        return
    try:
        import posthog
        posthog.api_key = key
        posthog.host    = host
        uid = user.get('id', 'anonymous')
        posthog.capture(uid, event, props or {})
    except Exception:
        pass  # analytics must never break the app


# ─── Island: Overview ─────────────────────────────────────────────────────────
@st.fragment
def render_overview():
    summary  = load_summary()
    daily_df = summary[summary['grain'] == 'daily'].copy()
    daily_df['dim_value'] = pd.to_datetime(daily_df['dim_value'])
    daily_df = daily_df.sort_values('dim_value')

    total_txns      = int(daily_df['txn_count'].sum())
    total_fraud     = int(daily_df['fraud_count'].sum())
    fraud_rate      = total_fraud / total_txns if total_txns else 0
    total_fraud_amt = daily_df['fraud_amt'].sum()

    st.title('Fraud Detection — Overview')
    col1, col2, col3, col4 = st.columns(4)
    col1.metric('Total Transactions', f'{total_txns:,}')
    col2.metric('Fraud Rate', f'{fraud_rate:.2%}')
    col3.metric('Fraud Transactions', f'{total_fraud:,}')
    col4.metric('Total Fraud Amount', f'${total_fraud_amt:,.0f}')
    st.divider()

    fig = go.Figure()
    fig.add_trace(go.Bar(x=daily_df['dim_value'], y=daily_df['txn_count'],
                         name='Total Transactions', marker_color='#4C72B0', opacity=0.7, yaxis='y1'))
    fig.add_trace(go.Scatter(x=daily_df['dim_value'], y=daily_df['fraud_rate_pct'],
                             name='Fraud Rate (%)', mode='lines',
                             line=dict(color='#DD8452', width=2), yaxis='y2'))
    fig.update_layout(
        title='Daily Transaction Volume & Fraud Rate',
        yaxis=dict(title='Transactions', showgrid=False),
        yaxis2=dict(title='Fraud Rate (%)', overlaying='y', side='right', showgrid=False),
        legend=dict(orientation='h', y=1.1), height=400, plot_bgcolor='white',
    )
    st.plotly_chart(fig, use_container_width=True)

    fig2 = px.area(daily_df, x='dim_value', y='fraud_amt',
                   title='Daily Fraud Amount ($)',
                   labels={'dim_value': 'Date', 'fraud_amt': 'Fraud Amount ($)'},
                   color_discrete_sequence=['#d62728'])
    fig2.update_layout(height=300, plot_bgcolor='white')
    st.plotly_chart(fig2, use_container_width=True)


# ─── Island: Risk Breakdown ───────────────────────────────────────────────────
@st.fragment
def render_risk_breakdown():
    summary    = load_summary()
    product_df = summary[summary['grain'] == 'product']
    card_df    = summary[summary['grain'] == 'card_type']
    email_df   = summary[summary['grain'] == 'email_domain']
    hour_df    = summary[summary['grain'] == 'hour_of_day'].copy()
    hour_df['dim_value'] = hour_df['dim_value'].astype(int)
    hour_df = hour_df.sort_values('dim_value')

    st.title('Risk Breakdown')
    col1, col2 = st.columns(2)
    with col1:
        fig = px.bar(product_df.sort_values('fraud_rate_pct', ascending=False),
                     x='dim_value', y='fraud_rate_pct', title='Fraud Rate by Product Code',
                     labels={'dim_value': 'Product', 'fraud_rate_pct': 'Fraud Rate (%)'},
                     color='fraud_rate_pct', color_continuous_scale='Reds', text='fraud_rate_pct')
        fig.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
        fig.update_layout(height=350, plot_bgcolor='white', showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig = px.bar(card_df.sort_values('fraud_rate_pct', ascending=False),
                     x='dim_value', y='fraud_rate_pct', title='Fraud Rate by Card Type',
                     labels={'dim_value': 'Card Type', 'fraud_rate_pct': 'Fraud Rate (%)'},
                     color='fraud_rate_pct', color_continuous_scale='Oranges', text='fraud_rate_pct')
        fig.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
        fig.update_layout(height=350, plot_bgcolor='white', showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    fig3 = px.bar(email_df.sort_values('fraud_rate_pct', ascending=True).tail(15),
                  x='fraud_rate_pct', y='dim_value', orientation='h',
                  title='Top 15 Email Domains by Fraud Rate',
                  labels={'dim_value': 'Email Domain', 'fraud_rate_pct': 'Fraud Rate (%)'},
                  color='fraud_rate_pct', color_continuous_scale='YlOrRd')
    fig3.update_layout(height=450, plot_bgcolor='white')
    st.plotly_chart(fig3, use_container_width=True)

    fig4 = px.bar(hour_df, x='dim_value', y='fraud_rate_pct',
                  title='Fraud Rate by Hour of Day',
                  labels={'dim_value': 'Hour', 'fraud_rate_pct': 'Fraud Rate (%)'},
                  color='fraud_rate_pct', color_continuous_scale='Blues')
    fig4.update_layout(height=300, plot_bgcolor='white')
    st.plotly_chart(fig4, use_container_width=True)


# ─── Island: Model Performance ────────────────────────────────────────────────
@st.fragment
def render_model_performance():
    st.title('Model Performance')
    result = load_model_data()
    if result is None:
        st.warning('Model not trained yet. Run `python src/train.py` first.')
        st.stop()

    artifact, df = result
    model     = artifact['model']
    feat_cols = [c for c in artifact['feature_cols'] if c in df.columns]

    n     = len(df)
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
        fig_roc = go.Figure()
        fig_roc.add_trace(go.Scatter(x=fpr, y=tpr, mode='lines',
                                     name=f'XGBoost (AUC={roc_auc:.3f})',
                                     line=dict(color='#DD8452', width=2)))
        fig_roc.add_trace(go.Scatter(x=[0,1], y=[0,1], mode='lines', name='Random',
                                     line=dict(color='gray', dash='dash')))
        fig_roc.update_layout(title='ROC Curve', xaxis_title='FPR', yaxis_title='TPR',
                               height=400, plot_bgcolor='white')
        st.plotly_chart(fig_roc, use_container_width=True)
    with right:
        cm = confusion_matrix(y_hold, preds)
        fig_cm = px.imshow(cm, text_auto=True,
                           labels=dict(x='Predicted', y='Actual', color='Count'),
                           x=['Legit', 'Fraud'], y=['Legit', 'Fraud'],
                           color_continuous_scale='Blues',
                           title='Confusion Matrix (threshold=0.5)')
        fig_cm.update_layout(height=400)
        st.plotly_chart(fig_cm, use_container_width=True)

    fi = pd.DataFrame({'feature': feat_cols, 'importance': model.feature_importances_}
                      ).sort_values('importance', ascending=False).head(20)
    fig_fi = px.bar(fi, x='importance', y='feature', orientation='h',
                    title='Top 20 Feature Importances',
                    color='importance', color_continuous_scale='Viridis')
    fig_fi.update_layout(height=500, plot_bgcolor='white',
                         yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig_fi, use_container_width=True)


# ─── Island: Transaction Explorer ─────────────────────────────────────────────
@st.fragment
def render_transaction_explorer():
    """Island: only this fragment rerenders when filters change.

    Security notes:
      - multiselect / selectbox only allow preset values from data — no free-text SQL surface.
      - Filtering runs in pandas, not SQL — no injection risk.
      - CSV export is rate-limited to 5 downloads/min per session.
    """
    st.title('Transaction Explorer')
    sample = load_sample()
    st.caption(f'Showing most recent {len(sample):,} transactions')

    col1, col2, col3 = st.columns(3)
    with col1:
        product_filter = st.multiselect('Product Code',
                                        options=sorted(sample['product_cd'].dropna().unique()))
    with col2:
        card_filter = st.multiselect('Card Type',
                                     options=sorted(sample['card6'].dropna().unique()))
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
    view = filtered[display_cols].rename(columns={'is_fraud': 'FRAUD'}).head(1000)

    st.dataframe(
        view, use_container_width=True,
        column_config={
            'FRAUD': st.column_config.NumberColumn(format='%d', help='1=Fraud, 0=Legit'),
            'transaction_amt': st.column_config.NumberColumn(format='$%.2f'),
        },
    )

    # ── Rate-limited CSV download ─────────────────────────────────────────────
    if check_rate_limit('export', max_calls=5, window_seconds=60):
        csv = view.to_csv(index=False).encode('utf-8')
        if st.download_button('Download filtered data (CSV)', csv,
                               'fraud_transactions.csv', 'text/csv'):
            _track('export_csv', {'rows': len(view), 'filters': {
                'product': product_filter, 'card': card_filter, 'fraud': fraud_filter,
            }})
    else:
        st.warning('Download limit reached (5 per minute). Please wait before exporting again.')


# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title('🔍 Fraud Pipeline')
    st.caption('IEEE-CIS Dataset • XGBoost Model')
    st.divider()
    st.markdown('**Navigate:**')
    tab_selection = st.radio(
        '', ['Overview', 'Risk Breakdown', 'Model Performance', 'Transaction Explorer'],
        label_visibility='collapsed',
    )
    st.divider()
    st.caption(f'Signed in as **{user["email"]}**')
    if st.button('Sign Out', use_container_width=True):
        sign_out()

# ─── Guard: verify data loads before rendering any island ─────────────────────
try:
    load_summary()
    load_sample()
except Exception as e:
    capture_exception(e, {'stage': 'data_load'})
    # Show a user-friendly message — never expose the raw exception
    st.error('Unable to load pipeline data. The data store may not be initialized.')
    st.info('Run `python src/ingest_data.py` then `dbt run` to build the database.')
    logger.exception('Data load failed')
    st.stop()

# ─── Track tab navigation ─────────────────────────────────────────────────────
_track('tab_viewed', {'tab': tab_selection})

# ─── Dispatch to the active island ────────────────────────────────────────────
try:
    if tab_selection == 'Overview':
        render_overview()
    elif tab_selection == 'Risk Breakdown':
        render_risk_breakdown()
    elif tab_selection == 'Model Performance':
        render_model_performance()
    elif tab_selection == 'Transaction Explorer':
        render_transaction_explorer()
except Exception as e:
    capture_exception(e, {'tab': tab_selection})
    logger.exception('Unhandled error in tab: %s', tab_selection)
    # Graceful error — no stack trace shown to the user
    st.error('Something went wrong loading this view. The issue has been reported.')
    st.info('Try refreshing the page. If the problem persists, contact support.')
