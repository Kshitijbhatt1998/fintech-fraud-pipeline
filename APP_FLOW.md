# Application Flow Documentation

> This document maps every data flow, every user path through the dashboard, and every decision point in the pipeline. It covers both the **data pipeline flow** (how data moves) and the **dashboard navigation flow** (how users explore results).

---

## 1. Entry Points

### Pipeline Entry Points
- **Full pipeline run**: User runs `python src/ingest_data.py` from project root
- **dbt only**: User runs `dbt run` inside `dbt_project/` (assumes DuckDB already populated)
- **Train only**: User runs `python src/train.py` (assumes `fraud_features` table exists)
- **Dashboard only**: User runs `streamlit run src/dashboard.py` (demo mode if no DuckDB)

### Dashboard Entry Points
- **Local**: `http://localhost:8501` after running `streamlit run src/dashboard.py`
- **Streamlit Cloud**: Public URL (Phase 2 deployment)
- **Demo Mode**: Automatically activated when `data/fraud.duckdb` does not exist — shows realistic synthetic data

---

## 2. Core Flows

### Flow 1: Full Pipeline Execution

**Goal**: Transform raw CSV files into a trained model and live dashboard
**Entry Point**: Project root directory, raw CSV files in `data/raw/`
**Frequency**: Once per dataset refresh or new data ingestion

#### Happy Path

1. **Step: Environment Setup**
   - User installs dependencies: `pip install -r requirements.txt`
   - User places Kaggle files in `data/raw/`
   - Files required: `train_transaction.csv`, `train_identity.csv`
   - Validation: Both files present and readable
   - Trigger: Run `python src/ingest_data.py`

2. **Step: Raw Ingestion** (`src/ingest_data.py`)
   - DuckDB connection created at `data/fraud.duckdb`
   - `raw_transactions` table created via `read_csv_auto`
   - `raw_identity` table created via `read_csv_auto`
   - Row counts printed to console: 590,540 transactions, 144,233 identity records
   - Trigger: Automatic continuation to cleaning step

3. **Step: Data Cleaning** (`src/ingest_data.py` → `clean_transactions`)
   - Null percentage computed per column
   - Columns >90% null dropped (non-mandatory only)
   - Timestamp parsed: `TransactionDT + epoch_anchor → transaction_ts`
   - `hour_of_day`, `day_of_week` extracted
   - `log_amt` computed
   - `has_identity` flag set via subquery join
   - M-flag columns string-encoded to integers
   - Output: `clean_transactions` table (590,540 rows)
   - Trigger: Ingestion script completes

4. **Step: dbt Run** (`cd dbt_project && dbt run`)
   - `stg_transactions` view created from `clean_transactions`
   - `stg_identity` view created from `clean_identity`
   - `fraud_features` mart table built with card stats and email stats CTEs
   - `fraud_summary` mart table built with 5 aggregation dimensions
   - Output: 4 models materialised
   - Trigger: User runs `dbt test`

5. **Step: dbt Test** (`dbt test`)
   - 12 tests executed across staging and marts layers
   - All tests must pass before proceeding
   - Output: "Finished running 12 tests. Passed: 12"
   - Trigger: User runs `python src/train.py`

6. **Step: Model Training** (`src/train.py`)
   - `fraud_features` table loaded from DuckDB (590,540 rows, 58 features)
   - Categorical columns label-encoded
   - 5-fold TimeSeriesSplit cross-validation executed
   - Final model fit on full dataset
   - Holdout evaluation on last 20% (time-based)
   - Model saved to `models/xgb_fraud_v1.pkl`
   - MLflow run logged to `mlruns/`
   - Output: AUC 0.9791 printed to console and logged to MLflow

7. **Step: Dashboard Launch** (`streamlit run src/dashboard.py`)
   - App connects to `data/fraud.duckdb`
   - Loads `fraud_summary` and sample of `fraud_features`
   - Loads `models/xgb_fraud_v1.pkl`
   - Dashboard available at `http://localhost:8501`

#### Error States

- **Missing raw CSV files**
  - Display: `FileNotFoundError` with path shown
  - Action: User downloads Kaggle data and places in `data/raw/`

- **DuckDB already exists**
  - Display: Silent — script calls `os.remove(DB_PATH)` before recreating
  - Action: None required, existing database is replaced

- **dbt test failure**
  - Display: `dbt test` output shows failing test name and column
  - Action: Inspect data quality issue, fix upstream cleaning step

- **Insufficient memory during training**
  - Display: Python `MemoryError`
  - Action: Close other applications; pipeline requires ~4GB RAM

#### Edge Cases
- User runs `python src/train.py` before `dbt run` → `Table 'fraud_features' not found` error — README instructs correct order
- User runs pipeline on Windows → path separators handled via `pathlib.Path` throughout
- MLflow port 5000 already in use → `mlflow ui` optional, tracking still works locally

---

### Flow 2: Dashboard Navigation

**Goal**: Explore fraud patterns and model performance interactively
**Entry Point**: `http://localhost:8501`
**Frequency**: Every analytical session

#### Screen: Sidebar
- **Elements**: Title, caption, navigation radio buttons
- **Options**: Overview | Risk Breakdown | Model Performance | Transaction Explorer
- **Behavior**: Selecting a tab renders that section in the main panel
- **State**: No state preserved between tab switches (Streamlit re-renders)

#### Screen: Overview Tab
- **Purpose**: High-level KPIs and daily trend lines
- **Elements**:
  - 4 metric cards: Total Transactions, Fraud Rate, Fraud Transactions, Total Fraud Amount
  - Dual-axis chart: Daily transaction volume (bars) + Fraud rate % (line)
  - Area chart: Daily fraud amount over time
- **Data Source**: `fraud_summary` WHERE grain = 'daily'
- **Actions Available**:
  - Hover charts → tooltips with exact values
  - No filtering on this tab (aggregate view only)
- **State Variants**:
  - Loading: Streamlit spinner
  - Demo Mode: Synthetic 180-day data displayed with info banner
  - Error: Red error box if DuckDB connection fails

#### Screen: Risk Breakdown Tab
- **Purpose**: Identify high-risk segments by product, card, email, and time
- **Elements**:
  - Bar chart: Fraud rate by product code (sorted descending)
  - Bar chart: Fraud rate by card type
  - Horizontal bar: Top 15 email domains by fraud rate
  - Bar chart: Fraud rate by hour of day (0–23)
- **Data Source**: `fraud_summary` WHERE grain IN ('product','card_type','email_domain','hour_of_day')
- **Actions Available**:
  - Hover bars → exact fraud rate percentage
  - No filtering (segment-level view)
- **State Variants**:
  - Loading: Streamlit spinner per chart
  - Empty: Not applicable (always has data from demo mode fallback)

#### Screen: Model Performance Tab
- **Purpose**: Evaluate XGBoost model quality on holdout data
- **Elements**:
  - 3 metric cards: Holdout AUC-ROC, Fraud Rate (holdout), Holdout sample count
  - ROC curve (Plotly): XGBoost line vs random baseline
  - Confusion matrix (Plotly heatmap): At threshold=0.5
  - Feature importance bar chart: Top 20 features
- **Data Source**: `models/xgb_fraud_v1.pkl` + `fraud_features` (last 20% of rows)
- **Decision Point**:
  ```
  IF models/xgb_fraud_v1.pkl does NOT exist
  THEN show: "Model not trained yet. Run python src/train.py first."
  AND stop rendering tab
  ELSE
  THEN load model, run predictions, render charts
  ```
- **State Variants**:
  - Model missing: Warning message shown
  - Demo Mode: Returns None from load_model_data() → same warning shown

#### Screen: Transaction Explorer Tab
- **Purpose**: Browse and filter individual transactions
- **Elements**:
  - Multiselect: Product Code filter
  - Multiselect: Card Type filter
  - Selectbox: Show All / Fraud only / Legitimate only
  - Count display: "X transactions match filters"
  - Dataframe: 1000 rows shown (of 50,000 loaded), with FRAUD column highlighted
- **Data Source**: `fraud_features` ORDER BY transaction_dt DESC LIMIT 50,000
- **Actions Available**:
  - Apply product filter → dataframe updates
  - Apply card type filter → dataframe updates
  - Select fraud/legit toggle → dataframe updates
- **State Variants**:
  - All filters clear: Shows all 50,000 rows (capped at 1000 displayed)
  - Filters applied: Shows matching count
  - No results: Shows "0 transactions match filters"

---

## 3. Navigation Map

```
Dashboard (localhost:8501)
├── Sidebar
│   └── Radio Navigation
│       ├── Overview
│       │   ├── KPI Metrics (4 cards)
│       │   ├── Daily Volume + Fraud Rate Chart
│       │   └── Daily Fraud Amount Chart
│       ├── Risk Breakdown
│       │   ├── Fraud Rate by Product Code
│       │   ├── Fraud Rate by Card Type
│       │   ├── Top 15 Email Domains
│       │   └── Fraud Rate by Hour of Day
│       ├── Model Performance
│       │   ├── AUC / Sample Metrics
│       │   ├── ROC Curve
│       │   ├── Confusion Matrix
│       │   └── Feature Importance (Top 20)
│       └── Transaction Explorer
│           ├── Filters (Product / Card / Fraud toggle)
│           ├── Match Count
│           └── Filtered Dataframe (1000 rows)
```

### Navigation Rules
- **No authentication required**: Dashboard is fully public when running locally
- **Demo mode fallback**: All tabs work without `fraud.duckdb` present
- **Model Performance exception**: Requires `models/xgb_fraud_v1.pkl` OR shows warning

---

## 4. Screen Inventory

### Screen: Overview
- **Route**: Default (radio = 'Overview')
- **Access**: Public
- **Purpose**: Executive summary of fraud pipeline results
- **Key Elements**: 4 KPI cards, 2 Plotly charts
- **State Variants**: Loading (spinner), Demo (synthetic data + info banner), Live (DuckDB data)

### Screen: Risk Breakdown
- **Route**: Radio = 'Risk Breakdown'
- **Access**: Public
- **Purpose**: Segment-level fraud rate analysis
- **Key Elements**: 4 Plotly bar charts
- **State Variants**: Loading (spinner per chart), Demo, Live

### Screen: Model Performance
- **Route**: Radio = 'Model Performance'
- **Access**: Public
- **Purpose**: Validate XGBoost model quality
- **Key Elements**: 3 metrics, ROC curve, confusion matrix, feature importance
- **State Variants**: Model missing (warning + stop), Loading, Live

### Screen: Transaction Explorer
- **Route**: Radio = 'Transaction Explorer'
- **Access**: Public
- **Purpose**: Browse individual transactions with fraud labels
- **Key Elements**: 3 filters, count label, 1000-row dataframe
- **State Variants**: Unfiltered, Filtered, No results

---

## 5. Decision Points

### Decision: Demo Mode vs Live Mode
```
IF data/fraud.duckdb does NOT exist
THEN DEMO_MODE = True
AND load_summary() returns synthetic 180-day data
AND load_sample() returns synthetic 5000 transactions
AND show info banner: "Demo Mode — full pipeline processes 590,540 real transactions"
ELSE
THEN DEMO_MODE = False
AND load_summary() queries fraud_summary table
AND load_sample() queries fraud_features table
```

### Decision: Model Performance Tab Rendering
```
IF DEMO_MODE = True
THEN load_model_data() returns None
AND show warning: "Model not trained yet"
AND st.stop() — no further rendering
ELSE IF models/xgb_fraud_v1.pkl does NOT exist
THEN show warning: "Model not trained yet. Run python src/train.py first."
AND st.stop()
ELSE
THEN load model + feature data
AND render ROC curve, confusion matrix, feature importance
```

### Decision: Transaction Explorer Filters
```
IF product_filter is not empty
THEN filter dataframe WHERE product_cd IN (selected values)

IF card_filter is not empty
THEN filter dataframe WHERE card6 IN (selected values)

IF fraud_filter = 'Fraud only'
THEN filter WHERE is_fraud = 1
ELSE IF fraud_filter = 'Legitimate only'
THEN filter WHERE is_fraud = 0
ELSE
THEN show all rows (no fraud filter)
```

### Decision: dbt Model Materialisation
```
IF model is in staging/
THEN materialized = view (no storage, always fresh)

IF model is in marts/
THEN materialized = table (stored, optimised for query)
```

---

## 6. Error Handling Flows

### Pipeline Error: Missing Raw Data
- **Display**: `FileNotFoundError: [Errno 2] No such file or directory: 'data/raw/train_transaction.csv'`
- **Actions**: README directs user to Kaggle download page
- **Recovery**: Place files in correct directory, re-run script

### Pipeline Error: DuckDB Table Not Found During Training
- **Display**: `duckdb.CatalogException: Table with name fraud_features does not exist`
- **Actions**: IMPLEMENTATION_PLAN.md Step 3 explains correct execution order
- **Recovery**: Run `dbt run` inside `dbt_project/` before running `python src/train.py`

### Dashboard Error: Database Connection Failure
- **Display**: Streamlit red error box: "Could not connect to fraud.duckdb: [error]"
- **Actions**: Info box shown with instructions to run notebook + `dbt run`
- **Recovery**: `st.stop()` prevents further rendering

### dbt Error: Test Failure
- **Display**: dbt CLI output with failing test name, model, and column
- **Actions**: Check data quality in DuckDB using Python or dbt debug
- **Recovery**: Fix upstream cleaning logic in `src/ingest_data.py`, re-run pipeline

---

## 7. Data Flow Map

```
data/raw/train_transaction.csv  ─────┐
data/raw/train_identity.csv     ─────┤
                                     ▼
                          [src/ingest_data.py]
                          DuckDB: raw_transactions
                          DuckDB: raw_identity
                                     │
                          [Cleaning Logic]
                          DuckDB: clean_transactions
                          DuckDB: clean_identity
                                     │
                          [dbt staging/]
                          View: stg_transactions
                          View: stg_identity
                                     │
                          [dbt marts/]
                          Table: fraud_features  ──────► models/xgb_fraud_v1.pkl
                          Table: fraud_summary   ──────► src/dashboard.py
                                     │
                          [Output Formats]
                          fraud_features.parquet
                          HuggingFace Dataset
```

---

## 8. Caching Behavior

### Streamlit Cache Strategy
- `load_summary()` — cached with `@st.cache_data(ttl=300)` — refreshes every 5 minutes
- `load_sample()` — cached with `@st.cache_data(ttl=300)` — refreshes every 5 minutes
- `load_model_data()` — cached with `@st.cache_data(ttl=600)` — refreshes every 10 minutes
- Cache is per-session, not shared across users
- Demo mode data generated with fixed `np.random.seed` for reproducibility
