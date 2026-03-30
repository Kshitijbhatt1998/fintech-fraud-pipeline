# Technology Stack Documentation

## 1. Stack Overview
**Last Updated**: 2026-03-30
**Version**: 1.0
**Python**: 3.10

### Architecture Pattern
- **Type**: Single-machine batch pipeline
- **Pattern**: Medallion Architecture (Bronze → Silver → Gold via dbt)
- **Deployment**: Local execution; output published to HuggingFace Datasets

---

## 2. Data Layer

### Storage Engine
- **Tool**: DuckDB
- **Version**: `>=0.10.0`
- **File**: `data/fraud.duckdb` (single-file columnar database)
- **Reason**: In-process columnar OLAP engine — no server, no config, processes 600K rows in <30s on laptop. Supports Parquet, CSV, and SQL natively.
- **Documentation**: https://duckdb.org/docs/
- **License**: MIT
- **Alternatives Considered**: SQLite (rejected: row-oriented, slow for analytics), PostgreSQL (rejected: requires server infrastructure)

### Data Formats
- **Ingestion**: CSV via `read_csv_auto` (schema auto-detected)
- **Storage**: DuckDB native columnar format
- **Export**: Parquet (primary), CSV, JSONL
- **HuggingFace**: Parquet (auto-converted by HF for dataset viewer)

---

## 3. Transformation Layer

### Transformation Framework
- **Tool**: dbt (data build tool)
- **Version**: `dbt-core>=1.7.0`
- **Adapter**: `dbt-duckdb>=1.7.0`
- **Profile**: `fraud_pipeline` (configured in `dbt_project/profiles.yml`)
- **Reason**: SQL-first transformations with built-in testing, documentation, and lineage tracking. Industry standard for data engineering.
- **Documentation**: https://docs.getdbt.com/
- **License**: Apache 2.0

### dbt Project Structure
```
dbt_project/
├── models/
│   ├── staging/          # Silver layer (views)
│   │   ├── stg_transactions.sql
│   │   ├── stg_identity.sql
│   │   └── sources.yml
│   └── marts/            # Gold layer (tables)
│       ├── fraud_features.sql
│       └── fraud_summary.sql
├── tests/
│   └── schema.yml        # 12 data quality tests
├── dbt_project.yml
└── profiles.yml
```

### Materialisation Strategy
| Layer | Type | Reason |
|-------|------|--------|
| `staging/*` | View | No storage cost, always reads fresh from source |
| `marts/*` | Table | Pre-computed for dashboard and ML training speed |

---

## 4. Machine Learning Layer

### ML Framework
- **Library**: XGBoost
- **Version**: `>=2.0.0`
- **Reason**: Best-in-class gradient boosting for tabular fraud data. Handles class imbalance via `scale_pos_weight`. Native support for missing values.
- **Documentation**: https://xgboost.readthedocs.io/
- **License**: Apache 2.0

### Model Evaluation
- **Library**: scikit-learn
- **Version**: `>=1.4.0`
- **Components Used**:
  - `TimeSeriesSplit` — temporal cross-validation (prevents data leakage)
  - `roc_auc_score` — primary metric
  - `average_precision_score` — secondary metric (handles class imbalance)
  - `LabelEncoder` — categorical feature encoding
  - `classification_report`, `confusion_matrix` — evaluation reporting
- **Documentation**: https://scikit-learn.org/
- **License**: BSD-3

### Experiment Tracking
- **Tool**: MLflow
- **Version**: `>=2.10.0`
- **Tracking**: Local filesystem (`mlruns/` directory)
- **Logged Per Run**:
  - Params: n_estimators, learning_rate, max_depth, scale_pos_weight, n_features
  - Metrics: cv_mean_auc, cv_mean_ap, holdout_auc, holdout_ap, fold_1–5_auc
  - Artifacts: xgb_fraud_v1.pkl
- **Documentation**: https://mlflow.org/docs/
- **License**: Apache 2.0

### Model Persistence
- **Format**: Python pickle (`.pkl`)
- **Contents**: `{'model': XGBClassifier, 'feature_cols': List[str]}`
- **Path**: `models/xgb_fraud_v1.pkl`

---

## 5. Dashboard Layer

### Dashboard Framework
- **Tool**: Streamlit
- **Version**: `>=1.35.0`
- **Reason**: Fastest path from Python data to interactive dashboard. No frontend code required.
- **Documentation**: https://docs.streamlit.io/
- **License**: Apache 2.0

### Charting Library
- **Library**: Plotly
- **Version**: `>=5.20.0`
- **Components Used**:
  - `plotly.express` — bar charts, area charts, scatter plots, heatmaps
  - `plotly.graph_objects` — dual-axis charts, ROC curves
- **Documentation**: https://plotly.com/python/
- **License**: MIT

### Caching
- `@st.cache_data(ttl=300)` — data queries cached 5 minutes
- `@st.cache_data(ttl=600)` — model artifact cached 10 minutes

---

## 6. Core Data Libraries

### DataFrame Processing
- **Library**: pandas
- **Version**: `>=2.0.0`
- **Use**: Loading DuckDB results, null percentage computation, label encoding
- **License**: BSD-3

### Numerical Computing
- **Library**: NumPy
- **Version**: `>=1.26.0`
- **Use**: Cross-validation score arrays, ROC curve computation
- **License**: BSD-3

---

## 7. DevOps & Infrastructure

### Version Control
- **System**: Git
- **Platform**: GitHub
- **Repository**: https://github.com/Kshitijbhatt1998/fintech-fraud-pipeline
- **Branch Strategy**:
  - `main` — stable, published state
  - Feature branches for additions

### Dataset Hosting
- **Platform**: HuggingFace Datasets
- **Dataset**: https://huggingface.co/datasets/Kshitijbhatt1998/ieee-fraud-detection-pipeline-features
- **Format**: Parquet (35.1 MB)
- **SDK**: `huggingface_hub>=0.20.0`

### CI/CD (Phase 2)
- **Platform**: GitHub Actions
- **Planned Workflows**:
  - dbt test on PR
  - Lint check on PR

---

## 8. Development Environment

### Runtime
- **Language**: Python
- **Version**: 3.10
- **Package Manager**: pip
- **Virtual Environment**: `.venv` (venv)

### OS Compatibility
- Windows 10/11 ✅ (primary dev environment)
- macOS ✅
- Ubuntu/Linux ✅

### IDE Recommendations
- **Editor**: VS Code or PyCharm
- **Extensions**: Python, Pylance, dbt Power User

---

## 9. Environment Variables

```bash
# No secrets required for local pipeline execution
# All data is local filesystem

# Optional: MLflow remote tracking (not used by default)
# MLFLOW_TRACKING_URI="http://localhost:5000"

# Optional: HuggingFace upload
# HF_TOKEN="hf_..."  # Only needed for dataset uploads
```

---

## 10. Key Scripts

```bash
# Full pipeline
python src/ingest_data.py              # Step 1: Ingest + clean
cd dbt_project && dbt run              # Step 2: Transform
cd dbt_project && dbt test             # Step 2b: Validate
python src/train.py                    # Step 3: Train model

# Dashboard
streamlit run src/dashboard.py         # Launch at localhost:8501

# Export
python -c "import duckdb; con = duckdb.connect('data/fraud.duckdb', read_only=True); con.execute(\"COPY fraud_features TO 'fraud_features.parquet' (FORMAT PARQUET)\")"

# MLflow UI
mlflow ui                              # View experiments at localhost:5000
```

---

## 11. Dependencies Lock

```
# requirements.txt
duckdb>=0.10.0
pandas>=2.0.0
numpy>=1.26.0
dbt-core>=1.7.0
dbt-duckdb>=1.7.0
xgboost>=2.0.0
scikit-learn>=1.4.0
mlflow>=2.10.0
streamlit>=1.35.0
plotly>=5.20.0
python-dotenv>=1.0.0
huggingface_hub>=0.20.0
```
