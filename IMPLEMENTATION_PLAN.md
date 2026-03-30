# Implementation Plan

## Overview
- **Project**: Fintech Fraud Detection Data Pipeline
- **MVP Status**: Complete
- **Build Philosophy**: Documentation-first. Every step references PRD.md, APP_FLOW.md, TECH_STACK.md, FRONTEND_GUIDELINES.md, or BACKEND_STRUCTURE.md.

---

## Phase 1: Project Setup & Foundation

### Step 1.1: Clone Repository and Install Dependencies
**Duration**: 5 minutes
**Goal**: Reproducible environment on any machine

**Tasks**:
```bash
git clone https://github.com/Kshitijbhatt1998/fintech-fraud-pipeline.git
cd fintech-fraud-pipeline

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (macOS/Linux)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

**Success Criteria**:
- [ ] `python --version` shows 3.10.x
- [ ] `import duckdb` succeeds in Python
- [ ] `dbt --version` shows dbt-core 1.7.x
- [ ] `import xgboost` succeeds in Python
- [ ] `streamlit --version` succeeds

**Reference**: TECH_STACK.md § 8 Development Environment

---

### Step 1.2: Download Source Data
**Duration**: 10–20 minutes (depends on Kaggle connection speed)
**Goal**: Raw CSV files in correct location

**Tasks**:
1. Log in to [kaggle.com/c/ieee-fraud-detection/data](https://www.kaggle.com/c/ieee-fraud-detection/data)
2. Download: `train_transaction.csv`, `train_identity.csv`
3. Place in project:
```
data/
└── raw/
    ├── train_transaction.csv   # ~500MB
    └── train_identity.csv      # ~50MB
```

**Success Criteria**:
- [ ] `data/raw/train_transaction.csv` exists and is ~500MB
- [ ] `data/raw/train_identity.csv` exists and is ~50MB
- [ ] `wc -l data/raw/train_transaction.csv` shows 590,541 lines (header + 590,540 rows)

**Reference**: PRD.md § 9 Dependencies & Constraints

---

## Phase 2: Data Ingestion & Cleaning

### Step 2.1: Run Ingestion Script
**Duration**: 2–3 minutes
**Goal**: Populate DuckDB with raw and cleaned tables

**Tasks**:
```bash
python src/ingest_data.py
```

**Expected Console Output**:
```
Connecting to .../data/fraud.duckdb...
Ingesting raw transactions...
  Loaded 590,540 rows into raw_transactions (X.Xs)
Ingesting raw identity...
  Loaded 144,233 rows into raw_identity (X.Xs)
Cleaning transactions...
  Created clean_transactions: 590,540 rows
Cleaning identity...
  Created clean_identity: 144,233 rows
Ingestion complete.
```

**Success Criteria**:
- [ ] `data/fraud.duckdb` file created (~150–300MB)
- [ ] Console shows 590,540 rows in raw_transactions
- [ ] Console shows 144,233 rows in raw_identity
- [ ] Console shows 590,540 rows in clean_transactions
- [ ] No Python errors or stack traces
- [ ] Verify in Python:
```python
import duckdb
con = duckdb.connect('data/fraud.duckdb', read_only=True)
print(con.execute("SELECT COUNT(*) FROM clean_transactions").fetchone())
# Expected: (590540,)
print(con.execute("SELECT COUNT(*) FROM clean_transactions WHERE transaction_ts IS NULL").fetchone())
# Expected: (0,)  -- timestamp parsing worked
```

**Reference**: BACKEND_STRUCTURE.md § 2 DuckDB Schema, APP_FLOW.md § 2 Flow 1

---

### Step 2.2: Verify Cleaned Schema
**Duration**: 2 minutes
**Goal**: Confirm cleaning logic produced expected columns

**Tasks**:
```python
import duckdb, pandas as pd
con = duckdb.connect('data/fraud.duckdb', read_only=True)

# Check engineered columns exist
schema = con.execute("DESCRIBE clean_transactions").df()
print(schema[['column_name', 'column_type']].to_string())

# Spot-check feature values
sample = con.execute("""
    SELECT transaction_ts, hour_of_day, day_of_week, log_amt, has_identity,
           M1_enc, M4_enc
    FROM clean_transactions LIMIT 5
""").df()
print(sample)
con.close()
```

**Success Criteria**:
- [ ] `transaction_ts` column present and type TIMESTAMP
- [ ] `hour_of_day` values in range 0–23
- [ ] `day_of_week` values in range 0–6
- [ ] `log_amt` values > 0 for all non-zero amounts
- [ ] `M1_enc` values are 0, 1, or NULL (no string 'T'/'F' remaining)
- [ ] `M4_enc` values are 0, 1, 2, or NULL

**Reference**: BACKEND_STRUCTURE.md § 2 clean_transactions schema

---

## Phase 3: dbt Transformation

### Step 3.1: Configure dbt Profile
**Duration**: 2 minutes
**Goal**: Verify dbt can connect to DuckDB

**Tasks**:
Confirm `dbt_project/profiles.yml` contains:
```yaml
fraud_pipeline:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: '../data/fraud.duckdb'
```

```bash
cd dbt_project
dbt debug
```

**Success Criteria**:
- [ ] `dbt debug` shows "All checks passed"
- [ ] Connection test passes for DuckDB file

---

### Step 3.2: Run dbt Models
**Duration**: 1–2 minutes
**Goal**: Build all 4 dbt models

**Tasks**:
```bash
# From dbt_project/ directory
dbt run
```

**Expected Output**:
```
Running with dbt=1.7.x
Found 4 models, 13 tests, 2 sources

Concurrency: 1 threads

1 of 4 START sql view model main.stg_transactions .......... [RUN]
1 of 4 OK created sql view model main.stg_transactions ..... [OK in X.XXs]
2 of 4 START sql view model main.stg_identity .............. [RUN]
2 of 4 OK created sql view model main.stg_identity ......... [OK in X.XXs]
3 of 4 START sql table model main.fraud_features ........... [RUN]
3 of 4 OK created sql table model main.fraud_features ...... [OK in X.XXs]
4 of 4 START sql table model main.fraud_summary ............ [RUN]
4 of 4 OK created sql table model main.fraud_summary ....... [OK in X.XXs]

Finished running 4 models.
```

**Success Criteria**:
- [ ] All 4 models show `OK`
- [ ] No `ERROR` or `SKIP` in output
- [ ] Verify fraud_features:
```python
con = duckdb.connect('data/fraud.duckdb', read_only=True)
print(con.execute("SELECT COUNT(*), COUNT(DISTINCT transaction_id) FROM fraud_features").fetchone())
# Expected: (590540, 590540) — no duplicates
print(con.execute("SELECT COUNT(*) FROM fraud_features WHERE is_fraud IS NULL").fetchone())
# Expected: (0,) — label always present
```

**Reference**: BACKEND_STRUCTURE.md § 2 fraud_features schema, TECH_STACK.md § 3 Transformation Layer

---

### Step 3.3: Run dbt Tests
**Duration**: 1 minute
**Goal**: Validate all 12 data quality assertions

**Tasks**:
```bash
# From dbt_project/ directory
dbt test
```

**Expected Output**:
```
Running 13 tests
...
Finished running 13 tests.

Completed successfully

Done. PASS=13 WARN=0 ERROR=0 SKIP=0 TOTAL=13
```

**Success Criteria**:
- [ ] `PASS=13 ERROR=0` (or 12 depending on sources.yml count)
- [ ] Zero failing tests before proceeding to training
- [ ] If any test fails: inspect with `dbt test --select [test_name]` and fix upstream

**Reference**: BACKEND_STRUCTURE.md § 4 dbt Data Quality Tests, PRD.md § 12 Non-Functional Requirements

---

## Phase 4: Model Training

### Step 4.1: Train XGBoost Model
**Duration**: 3–5 minutes
**Goal**: Trained model saved to `models/xgb_fraud_v1.pkl` with AUC ≥ 0.97

**Tasks**:
```bash
# From project root
python src/train.py
```

**Expected Console Output**:
```
2024-XX-XX INFO Loading features from .../data/fraud.duckdb
2024-XX-XX INFO Loaded 590,540 rows x 58 cols
2024-XX-XX INFO Feature matrix: 590,540 rows x 58 features
2024-XX-XX INFO Fraud rate: 3.50%
2024-XX-XX INFO Starting 5-fold time-series cross-validation...
2024-XX-XX INFO   Fold 1: AUC=0.XXXX  AP=0.XXXX
2024-XX-XX INFO   Fold 2: AUC=0.XXXX  AP=0.XXXX
2024-XX-XX INFO   Fold 3: AUC=0.XXXX  AP=0.XXXX
2024-XX-XX INFO   Fold 4: AUC=0.XXXX  AP=0.XXXX
2024-XX-XX INFO   Fold 5: AUC=0.XXXX  AP=0.XXXX
2024-XX-XX INFO CV Mean AUC: 0.9791 (+/- 0.XXXX)
2024-XX-XX INFO Fitting final model on full training set...
2024-XX-XX INFO Holdout AUC: 0.9791  AP: 0.XXXX
2024-XX-XX INFO Model saved to .../models/xgb_fraud_v1.pkl
2024-XX-XX INFO MLflow run ID: [uuid]
```

**Success Criteria**:
- [ ] `models/xgb_fraud_v1.pkl` created
- [ ] CV Mean AUC ≥ 0.97
- [ ] Holdout AUC ≥ 0.97
- [ ] MLflow run logged (verify in `mlruns/` directory)
- [ ] No memory errors (requires ~4GB RAM)

**Reference**: BACKEND_STRUCTURE.md § 3 train.py, PRD.md § 6 Feature: XGBoost Model Training

---

### Step 4.2: Verify MLflow Experiment
**Duration**: 2 minutes
**Goal**: Confirm experiment metrics are logged

**Tasks**:
```bash
mlflow ui
# Open http://localhost:5000 in browser
```

**Success Criteria**:
- [ ] `fraud_detection` experiment visible
- [ ] `xgb_baseline` run listed
- [ ] `cv_mean_auc` and `holdout_auc` values match console output
- [ ] `xgb_fraud_v1.pkl` artifact listed under run

**Reference**: BACKEND_STRUCTURE.md § 5 MLflow Experiment Structure

---

## Phase 5: Dashboard

### Step 5.1: Launch Streamlit Dashboard
**Duration**: 30 seconds
**Goal**: All 4 tabs render correctly

**Tasks**:
```bash
# From project root
streamlit run src/dashboard.py
# Opens http://localhost:8501
```

**Tab Verification Checklist**:

**Overview tab**:
- [ ] 4 KPI metric cards visible
- [ ] Total Transactions shows ~590,540 (or close for demo mode)
- [ ] Daily volume + fraud rate dual-axis chart renders
- [ ] Daily fraud amount area chart renders

**Risk Breakdown tab**:
- [ ] Product code bar chart shows 5 bars (W/H/C/S/R)
- [ ] Card type bar chart renders
- [ ] Email domain horizontal bar shows 15 entries
- [ ] Hour-of-day bar chart shows 24 bars (0–23)

**Model Performance tab**:
- [ ] Holdout AUC-ROC shows 0.9791
- [ ] ROC curve renders with XGBoost line and random baseline
- [ ] Confusion matrix heatmap renders
- [ ] Feature importance bar chart shows 20 features

**Transaction Explorer tab**:
- [ ] Product Code multiselect populated
- [ ] Card Type multiselect populated
- [ ] Dataframe shows 1000 rows
- [ ] Fraud filter "Fraud only" reduces row count to ~3.5% of total

**Reference**: FRONTEND_GUIDELINES.md, APP_FLOW.md § 2 Flow 2

---

## Phase 6: Dataset Publication

### Step 6.1: Export Parquet
**Duration**: 1 minute
**Goal**: `fraud_features.parquet` file ready for upload

**Tasks**:
```python
import duckdb
con = duckdb.connect('data/fraud.duckdb', read_only=True)
con.execute("COPY fraud_features TO 'fraud_features.parquet' (FORMAT PARQUET)")
count = con.execute('SELECT COUNT(*) FROM fraud_features').fetchone()[0]
print(f'Exported {count:,} rows')
con.close()
```

**Success Criteria**:
- [ ] `fraud_features.parquet` created (~35MB)
- [ ] Row count confirms 590,540

---

### Step 6.2: Upload to HuggingFace
**Duration**: 5 minutes
**Goal**: Dataset live at huggingface.co/datasets/Kshitijbhatt1998/ieee-fraud-detection-pipeline-features

**Tasks**:
```python
from huggingface_hub import HfApi, login
login()  # Enter HF token from huggingface.co/settings/tokens

api = HfApi()
api.upload_file(
    path_or_fileobj='fraud_features.parquet',
    path_in_repo='fraud_features.parquet',
    repo_id='Kshitijbhatt1998/ieee-fraud-detection-pipeline-features',
    repo_type='dataset'
)
api.upload_file(
    path_or_fileobj='HUGGINGFACE_CARD.md',
    path_in_repo='README.md',
    repo_id='Kshitijbhatt1998/ieee-fraud-detection-pipeline-features',
    repo_type='dataset'
)
```

**Success Criteria**:
- [ ] Dataset card renders at HuggingFace URL
- [ ] Row count shows 590,540
- [ ] Task tag shows "Tabular Classification"
- [ ] License shows "Apache 2.0"

---

## Milestones

### Milestone 1: Pipeline Foundation Complete
**Target**: Day 1
**Deliverables**:
- [ ] Environment installed
- [ ] Raw data downloaded
- [ ] DuckDB populated with clean_transactions

### Milestone 2: dbt Layer Complete
**Target**: Day 1
**Deliverables**:
- [ ] All 4 dbt models built successfully
- [ ] All 12+ dbt tests passing
- [ ] fraud_features table available for training

### Milestone 3: Model Trained
**Target**: Day 1
**Deliverables**:
- [ ] xgb_fraud_v1.pkl saved
- [ ] Holdout AUC ≥ 0.97
- [ ] MLflow run logged

### Milestone 4: MVP Complete
**Target**: Day 1
**Deliverables**:
- [ ] Dashboard running on localhost:8501
- [ ] All 4 tabs verified
- [ ] HuggingFace dataset published
- [ ] All 8 documentation files committed to GitHub

---

## Risk Mitigation

### Technical Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| DuckDB version incompatibility | High | Pin `duckdb>=0.10.0` in requirements.txt |
| Memory error during training | High | Close other apps; pipeline needs ~4GB RAM |
| dbt profile path incorrect | Medium | Verify `../data/fraud.duckdb` relative path in profiles.yml |
| M-flag encoding produces wrong values | Medium | Validate M1_enc sample values after ingestion (Step 2.2) |
| XGBoost AUC below 0.97 | Low | Fixed random_state=42 ensures reproducibility |

### Timeline Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Kaggle data download slow | Medium | ~500MB — allow 20 min on slow connection |
| HuggingFace upload timeout | Low | Script auto-retries; 35MB file typically uploads in <2 min |
| dbt tests reveal data issue | Medium | Fix in ingest_data.py → re-run from Step 2.1 |

---

## Success Criteria (Overall)

### Pipeline is successful when:
1. ✅ All P0 features from PRD.md implemented
2. ✅ All data flows from APP_FLOW.md working end-to-end
3. ✅ Tech stack matches TECH_STACK.md (correct versions)
4. ✅ Dashboard matches FRONTEND_GUIDELINES.md (charts, colours, layout)
5. ✅ All tables match BACKEND_STRUCTURE.md schema exactly
6. ✅ All 12+ dbt tests passing
7. ✅ Holdout AUC ≥ 0.9791
8. ✅ Full pipeline runtime < 5 minutes
9. ✅ HuggingFace dataset live with 590,540 rows
10. ✅ All 8 documentation files committed to GitHub

---

## Post-MVP Roadmap

### After MVP launch, prioritize:
1. Streamlit Cloud deployment (public dashboard URL for client demos)
2. GitHub Actions CI (dbt test on every PR)
3. First 3 discovery calls → custom pipeline engagement
4. Second case study (credit scoring or AML domain)
5. P1 features: JSONL export, configurable null threshold
