# Frontend Guidelines

> This document defines the design system, component patterns, layout rules, and visual standards for the Streamlit dashboard (`src/dashboard.py`). All UI decisions reference these guidelines.

---

## 1. Design Philosophy

- **Data-first**: Charts and metrics always above explanatory text
- **Zero noise**: No decorative elements that don't carry information
- **Fintech aesthetic**: Dark/neutral palette, professional, conservative — not consumer-app playful
- **Instant context**: A user should understand what they're looking at within 3 seconds of a tab loading

---

## 2. Layout System

### Page Configuration
```python
st.set_page_config(
    page_title='Fraud Detection Pipeline',
    page_icon='🔍',
    layout='wide',
    initial_sidebar_state='expanded',
)
```

### Grid System
- **Wide layout**: Full browser width used
- **2-column splits**: `col1, col2 = st.columns(2)` — equal width
- **3-column splits**: `col1, col2, col3 = st.columns(3)` — equal width
- **4-column KPIs**: `col1, col2, col3, col4 = st.columns(4)` — Overview tab only
- **Full width**: Single charts always span full width (`use_container_width=True`)

### Spacing Rules
- `st.divider()` after KPI metric row before charts
- `st.divider()` between distinct chart sections
- No manual `st.write("")` padding — use Streamlit's native spacing

---

## 3. Colour Palette

### Chart Colours (Plotly)
| Use | Colour | Hex |
|-----|--------|-----|
| Primary bars / volume | Steel blue | `#4C72B0` |
| Secondary line / fraud rate | Orange | `#DD8452` |
| Fraud amount / danger | Red | `#d62728` |
| Sequential (low risk) | Blues scale | Plotly `Blues` |
| Sequential (risk intensity) | Reds scale | Plotly `Reds` |
| Sequential (orange risk) | Oranges scale | Plotly `Oranges` |
| Multi-risk heatmap | Yellow-Orange-Red | Plotly `YlOrRd` |
| Feature importance | Viridis | Plotly `Viridis` |

### Chart Background
- All charts: `plot_bgcolor='white'`
- Grid lines: Hidden (`showgrid=False`) on dual-axis charts
- Legend: `orientation='h', y=1.1` (horizontal, above chart)

---

## 4. Typography

- **Page titles**: `st.title('...')` — one per tab
- **Section captions**: `st.caption('...')` — for sub-context (row counts, data dates)
- **Metric labels**: `st.metric(label, value)` — auto-styled by Streamlit
- **No custom fonts**: Use Streamlit defaults throughout
- **Code/SQL**: Never displayed in dashboard UI (backend only)

---

## 5. Component Patterns

### KPI Metric Row
```python
col1, col2, col3, col4 = st.columns(4)
col1.metric('Total Transactions', f'{total_txns:,}')
col2.metric('Fraud Rate', f'{fraud_rate:.2%}')
col3.metric('Fraud Transactions', f'{total_fraud:,}')
col4.metric('Total Fraud Amount', f'${total_fraud_amt:,.0f}')
```
- Always 3–4 metrics in a row
- Format: integers with comma separators, percentages with 2dp, currency with `$`
- No delta values (pipeline is not real-time)

### Dual-Axis Chart Pattern (Volume + Rate)
```python
fig = go.Figure()
fig.add_trace(go.Bar(
    x=dates, y=volume,
    name='Total Transactions',
    marker_color='#4C72B0', opacity=0.7, yaxis='y1'
))
fig.add_trace(go.Scatter(
    x=dates, y=fraud_rate,
    name='Fraud Rate (%)', mode='lines',
    line=dict(color='#DD8452', width=2), yaxis='y2'
))
fig.update_layout(
    yaxis=dict(title='Transactions', showgrid=False),
    yaxis2=dict(title='Fraud Rate (%)', overlaying='y', side='right', showgrid=False),
    legend=dict(orientation='h', y=1.1),
    height=400,
    plot_bgcolor='white',
)
```

### Bar Chart Pattern (Categorical Comparison)
```python
fig = px.bar(
    df.sort_values('fraud_rate_pct', ascending=False),
    x='dim_value', y='fraud_rate_pct',
    title='Fraud Rate by [Dimension]',
    color='fraud_rate_pct',
    color_continuous_scale='Reds',
    text='fraud_rate_pct',
)
fig.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
fig.update_layout(height=350, plot_bgcolor='white', showlegend=False)
```

### Horizontal Bar Chart Pattern (Rankings)
```python
fig = px.bar(
    df.sort_values('fraud_rate_pct', ascending=True).tail(15),
    x='fraud_rate_pct', y='dim_value', orientation='h',
    color='fraud_rate_pct', color_continuous_scale='YlOrRd',
)
fig.update_layout(height=450, plot_bgcolor='white')
```

### ROC Curve Pattern
```python
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=fpr, y=tpr, mode='lines',
    name=f'XGBoost (AUC={roc_auc:.3f})',
    line=dict(color='#DD8452', width=2)
))
fig.add_trace(go.Scatter(
    x=[0,1], y=[0,1], mode='lines',
    name='Random', line=dict(color='gray', dash='dash')
))
fig.update_layout(title='ROC Curve', xaxis_title='FPR', yaxis_title='TPR',
                  height=400, plot_bgcolor='white')
```

### Confusion Matrix Pattern
```python
fig = px.imshow(
    cm, text_auto=True,
    labels=dict(x='Predicted', y='Actual', color='Count'),
    x=['Legit', 'Fraud'], y=['Legit', 'Fraud'],
    color_continuous_scale='Blues',
    title='Confusion Matrix (threshold=0.5)',
)
fig.update_layout(height=400)
```

### Dataframe Pattern
```python
st.dataframe(
    df[display_cols].head(1000),
    use_container_width=True,
    column_config={
        'FRAUD': st.column_config.NumberColumn(format='%d', help='1=Fraud, 0=Legit'),
        'transaction_amt': st.column_config.NumberColumn(format='$%.2f'),
    }
)
```

---

## 6. Chart Heights

| Chart Type | Height |
|------------|--------|
| Dual-axis volume chart | 400px |
| Area chart | 300px |
| Categorical bar (2-col layout) | 350px |
| Horizontal bar (rankings) | 450px |
| Hourly bar | 300px |
| ROC curve | 400px |
| Confusion matrix | 400px |
| Feature importance | 500px |

---

## 7. Filter Controls

### Filter Row Pattern (Transaction Explorer)
```python
col1, col2, col3 = st.columns(3)
with col1:
    product_filter = st.multiselect('Product Code', options=sorted(df['product_cd'].dropna().unique()))
with col2:
    card_filter = st.multiselect('Card Type', options=sorted(df['card6'].dropna().unique()))
with col3:
    fraud_filter = st.selectbox('Show', ['All', 'Fraud only', 'Legitimate only'])
```
- Always in 3-column layout
- Multiselect for multi-value filters, selectbox for radio-style choice
- Options always sorted alphabetically
- No "Apply" button — Streamlit re-renders reactively

---

## 8. State & Loading Patterns

### Demo Mode Banner
```python
if not DB_PATH.exists():
    st.info(
        "**Demo Mode** — showing sample data. "
        "The full pipeline processes 590,540 real transactions with AUC 0.9791.",
        icon="ℹ️"
    )
```
- Always at top of page before any content
- `st.info()` with icon — never `st.warning()` (not an error state)

### Error State Pattern
```python
try:
    summary = load_summary()
    data_ok = True
except Exception as e:
    st.error(f'Could not connect to fraud.duckdb: {e}')
    st.info('Run notebook 02_data_pipeline.ipynb and `dbt run` first.')
    st.stop()
```
- `st.error()` for connection failures
- `st.info()` with recovery instructions immediately after
- `st.stop()` prevents partial render

### Missing Model Pattern
```python
if result is None:
    st.warning('Model not trained yet. Run `python src/train.py` first.')
    st.stop()
```
- `st.warning()` (not error) — model absence is expected in partial setups

---

## 9. Sidebar Design

```python
with st.sidebar:
    st.title('🔍 Fraud Pipeline')
    st.caption('IEEE-CIS Dataset • XGBoost Model')
    st.divider()
    st.markdown('**Navigate:**')
    tab_selection = st.radio(
        '', ['Overview', 'Risk Breakdown', 'Model Performance', 'Transaction Explorer'],
        label_visibility='collapsed'
    )
```
- Icon + title + caption always at top
- `st.divider()` between header and navigation
- Radio group with `label_visibility='collapsed'` — no redundant "Select a tab" label

---

## 10. Number Formatting Standards

| Data Type | Format | Example |
|-----------|--------|---------|
| Large integers | `f'{n:,}'` | 590,540 |
| Percentages | `f'{p:.2%}'` | 3.54% |
| Currency (large) | `f'${n:,.0f}'` | $1,234,567 |
| Currency (precise) | `f'$%.2f'` (column_config) | $142.50 |
| AUC / ratios | `f'{n:.4f}'` | 0.9791 |
| Chart percentage labels | `'%{text:.2f}%'` (Plotly) | 10.50% |
