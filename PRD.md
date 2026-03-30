# Product Requirements Document (PRD)

## 1. Product Overview
- **Project Title**: Fintech Fraud Detection Data Pipeline
- **Version**: 1.0
- **Last Updated**: 2026-03-30
- **Owner**: Kshitij Bhatt
- **Repository**: https://github.com/Kshitijbhatt1998/fintech-fraud-pipeline
- **HuggingFace Dataset**: https://huggingface.co/datasets/Kshitijbhatt1998/ieee-fraud-detection-pipeline-features

---

## 2. Problem Statement

Fintech AI teams building fraud detection, credit scoring, and AML models are bottlenecked at the data layer — not the model layer. Raw transaction data is messy: columns are 90%+ null, timestamps are in epoch offsets, categorical flags are inconsistent strings, and there is no feature engineering. Teams spend weeks building ingestion and cleaning logic before they can train a single model. There is no reusable, documented, production-adjacent pipeline they can learn from or adapt.

This project solves that by providing a complete, end-to-end data pipeline — from raw CSV ingestion to a clean 58-feature labeled dataset — that any fintech AI team can replicate or commission as a custom service.

---

## 3. Goals & Objectives

### Business Goals
- Demonstrate a production-grade fintech data pipeline as a public proof-of-work case study
- Generate discovery calls from fintech AI teams who need this kind of pipeline built for their data
- Establish credibility as a data pipeline specialist in the fintech AI market
- Target: 3 discovery calls within 30 days of launch

### User Goals
- ML engineers can clone the repo, run 3 commands, and have a model-ready feature dataset
- Fintech CTOs/founders can evaluate the quality of the pipeline work and assess fit for a custom engagement
- Data scientists can understand the feature engineering logic and adapt it to their domain

---

## 4. Success Metrics
- **Pipeline correctness**: All dbt tests pass (0 failures across 12 tests)
- **Model performance**: XGBoost holdout AUC ≥ 0.97 on IEEE-CIS dataset
- **Pipeline speed**: Full end-to-end run completes in < 5 minutes on standard laptop
- **Data scale**: Successfully processes 590,540 transactions + 144,233 identity records
- **Reproducibility**: Any developer can run `python src/ingest_data.py && dbt run && python src/train.py` without errors

---

## 5. Target Users & Personas

### Primary Persona: ML Engineer at Fintech Startup
- **Role**: Head of ML or founding ML engineer at a Series A–B fintech startup
- **Pain Points**: Spends 60–70% of time on data cleaning, not model work. No dedicated data engineer on team. Training data pipeline breaks silently. No feature store or data quality monitoring.
- **Goals**: Get clean, labeled, model-ready data fast. Want reproducible pipelines they can hand off. Need to ship fraud/credit models in weeks, not months.
- **Technical Proficiency**: High — comfortable with Python, SQL, MLflow. Familiar with XGBoost and dbt.

### Secondary Persona: CTO / Founder
- **Role**: Technical co-founder or CTO at early-stage fintech
- **Pain Points**: ML team is blocked on data quality. Hiring a full data engineer is expensive and slow. Not sure how to evaluate pipeline quality.
- **Goals**: Unblock the ML team. Understand what a production-grade data pipeline looks like. Evaluate whether to hire or contract out.
- **Technical Proficiency**: Medium — can read code, understands system architecture, doesn't write production Python day-to-day.

---

## 6. Features & Requirements

### Must-Have Features (P0)

1. **Raw Data Ingestion**
   - Description: Load raw CSV transaction and identity files into DuckDB with auto-schema detection
   - User Story: As an ML engineer, I want raw CSVs loaded into a queryable database so that I can start transforming data immediately without writing schema definitions
   - Acceptance Criteria:
     - [ ] `train_transaction.csv` (590,540 rows) loads without errors
     - [ ] `train_identity.csv` (144,233 rows) loads without errors
     - [ ] Schema auto-detected correctly for all columns
     - [ ] Load time < 60 seconds on standard hardware
   - Success Metric: Zero load errors, correct row counts confirmed

2. **Automated Data Cleaning**
   - Description: Drop columns with >90% null values, parse timestamps, encode categorical flags, engineer base features
   - User Story: As an ML engineer, I want null-heavy columns automatically removed so that my feature matrix doesn't have garbage inputs
   - Acceptance Criteria:
     - [ ] Columns exceeding 90% null threshold are dropped
     - [ ] Mandatory columns (TransactionID, isFraud, card1–6, C1–C14, D1–D15) are preserved regardless of null rate
     - [ ] `TransactionDT` converted to real UTC timestamp `transaction_ts`
     - [ ] `hour_of_day` and `day_of_week` engineered from timestamp
     - [ ] `log_amt` computed as `ln(TransactionAmt + 1)`
     - [ ] M-flag columns (M1–M9) encoded as integers
   - Success Metric: `clean_transactions` table produced with correct schema

3. **dbt Transformation Layer**
   - Description: Staging → marts transformation via dbt with data quality tests
   - User Story: As an ML engineer, I want SQL-based transformations that are testable and documented so that I can trust my training data
   - Acceptance Criteria:
     - [ ] `stg_transactions` view builds successfully
     - [ ] `stg_identity` view builds successfully
     - [ ] `fraud_features` mart table builds with all 58 features
     - [ ] `fraud_summary` mart table builds with all aggregation dimensions
     - [ ] All 12 dbt tests pass (unique, not_null, accepted_values)
   - Success Metric: `dbt test` returns 0 failures

4. **Feature Engineering**
   - Description: Card velocity features, email domain risk scores, amount anomaly ratio
   - User Story: As an ML engineer, I want pre-computed velocity and risk features so that my model has signal beyond raw transaction columns
   - Acceptance Criteria:
     - [ ] `card1_txn_count`, `card1_avg_amt`, `card1_historical_fraud_rate` computed per card
     - [ ] `email_txn_count`, `email_historical_fraud_rate` computed per email domain
     - [ ] `amt_vs_card_avg_ratio` computed for all transactions
     - [ ] `is_high_risk_product` flag set correctly for product_cd = 'W'
   - Success Metric: All engineered columns present and non-null for non-null inputs

5. **XGBoost Model Training**
   - Description: Time-series cross-validated XGBoost model with MLflow experiment tracking
   - User Story: As an ML engineer, I want a trained fraud model with tracked experiments so that I have a baseline to beat
   - Acceptance Criteria:
     - [ ] 5-fold TimeSeriesSplit cross-validation (no random shuffle)
     - [ ] CV mean AUC ≥ 0.97
     - [ ] Holdout AUC ≥ 0.97 on last 20% of data (time-based)
     - [ ] Model saved to `models/xgb_fraud_v1.pkl`
     - [ ] MLflow run logged with params, metrics, and artifact
   - Success Metric: Holdout AUC = 0.9791 (confirmed)

6. **Streamlit Dashboard**
   - Description: 4-tab interactive dashboard for pipeline results exploration
   - User Story: As a CTO, I want a visual dashboard so that I can understand fraud patterns and model performance without writing SQL
   - Acceptance Criteria:
     - [ ] Overview tab: KPIs + daily volume chart + daily fraud amount chart
     - [ ] Risk Breakdown tab: fraud rate by product, card type, email domain, hour
     - [ ] Model Performance tab: ROC curve, confusion matrix, feature importance
     - [ ] Transaction Explorer tab: filterable table with 50K rows
     - [ ] Demo mode works when `fraud.duckdb` is not present
   - Success Metric: Dashboard loads in < 3 seconds, all 4 tabs render without errors

### Should-Have Features (P1)

1. **HuggingFace Dataset Card**
   - Publish cleaned `fraud_features` dataset to HuggingFace with proper metadata, schema documentation, and benchmark results
   - Success Metric: Dataset discoverable via HuggingFace search with task category tags

2. **Parquet Export**
   - One-command export of `fraud_features` table to Parquet format
   - Success Metric: `fraud_features.parquet` exports correctly and matches row count

3. **GitHub Actions CI**
   - Automated dbt test run on every pull request
   - Success Metric: PRs automatically blocked if dbt tests fail

### Nice-to-Have Features (P2)

1. **Streamlit Cloud Deployment** — publicly accessible dashboard URL
2. **JSONL export format** — for direct LLM fine-tuning use cases
3. **Configurable null threshold** — CLI flag to override 90% default
4. **Incremental dbt models** — process only new transactions for production use

---

## 7. Explicitly OUT OF SCOPE

- Real-time/streaming fraud detection (batch pipeline only)
- REST API serving predictions
- User authentication or multi-tenant access
- Integration with live payment processors (Stripe, Adyen, etc.)
- Model retraining automation / scheduled pipelines
- Cloud deployment of the DuckDB database
- Support for test dataset (`test_transaction.csv`) — training data only
- Mobile-responsive dashboard
- Multi-currency or multi-jurisdiction support

---

## 8. User Scenarios

### Scenario 1: ML Engineer Replicating the Pipeline
- **Context**: Engineer at a fintech startup wants to evaluate the pipeline for potential adaptation
- **Steps**:
  1. Engineer clones repository from GitHub
  2. Installs dependencies via `pip install -r requirements.txt`
  3. Downloads IEEE-CIS data from Kaggle and places in `data/raw/`
  4. Runs `python src/ingest_data.py` — sees 590,540 rows loaded in < 60 seconds
  5. Runs `cd dbt_project && dbt run && dbt test` — sees all 12 tests pass
  6. Runs `python src/train.py` — sees AUC 0.9791 logged to MLflow
  7. Runs `streamlit run src/dashboard.py` — explores fraud patterns in dashboard
- **Expected Outcome**: Engineer successfully replicates full pipeline in under 30 minutes
- **Edge Cases**: Kaggle data download requires account; README links to data source

### Scenario 2: CTO Evaluating for Custom Engagement
- **Context**: CTO wants to see quality of work before booking a discovery call
- **Steps**:
  1. CTO visits GitHub repo, reads README
  2. Clicks HuggingFace dataset link — sees 590K rows, feature schema, benchmark
  3. Reviews DATA_PIPELINE.md — understands architecture and adaptability
  4. Sees contact link in README
  5. Books discovery call
- **Expected Outcome**: CTO has enough context to evaluate fit within 10 minutes
- **Edge Cases**: CTO may not have Python installed — dashboard demo mode handles this

### Scenario 3: Data Scientist Adapting Features
- **Context**: Data scientist wants to add a new feature to the pipeline
- **Steps**:
  1. Opens `dbt_project/models/marts/fraud_features.sql`
  2. Adds a new CTE for the feature logic
  3. Adds the column to the SELECT statement
  4. Runs `dbt run --select fraud_features`
  5. Adds a dbt test in `tests/schema.yml`
  6. Runs `dbt test --select fraud_features`
- **Expected Outcome**: New feature added and tested without touching Python code
- **Edge Cases**: New feature introduces nulls — dbt not_null test catches it

---

## 9. Dependencies & Constraints

- **Technical Constraints**: DuckDB operates as single-file, single-writer database — not suitable for concurrent writes in production
- **Data Constraints**: IEEE-CIS dataset requires Kaggle account to download; cannot be redistributed directly
- **Hardware Constraints**: Full pipeline requires ~4GB RAM for 590K transaction processing
- **Business Constraints**: Solo developer, no infrastructure budget — all tools must be free/open source
- **External Dependencies**: Kaggle (data source), HuggingFace (dataset hosting), MLflow (experiment tracking), Streamlit Cloud (dashboard hosting)

---

## 10. Timeline & Milestones

- **MVP (Completed)**: Pipeline runs end-to-end locally, model trained, dashboard working
- **Phase 1 (Completed 2026-03-30)**: README, DATA_PIPELINE.md, HuggingFace dataset, outreach materials
- **Phase 2 (Target: 2026-04-15)**: Streamlit Cloud deployment, LinkedIn content calendar, first 3 discovery calls
- **Phase 3 (Target: 2026-05-01)**: First paying client, custom pipeline delivery

---

## 11. Risks & Assumptions

### Risks
- **Risk**: HuggingFace dataset viewer timeout on large Parquet file — **Mitigation**: Added explicit `configs` YAML block to dataset card
- **Risk**: Kaggle TOS prevents redistribution of IEEE-CIS data — **Mitigation**: Distribute processed features only, link to original source
- **Risk**: DuckDB version incompatibility across environments — **Mitigation**: Pinned to `duckdb>=0.10.0` in requirements.txt
- **Risk**: MLflow experiment tracking folder grows large — **Mitigation**: `.gitignore` excludes `mlruns/` artifact binaries

### Assumptions
- Users have Python 3.10+ installed
- Users have 4GB+ RAM available for pipeline execution
- Kaggle IEEE-CIS dataset structure has not changed since 2019
- DuckDB single-file approach is acceptable for demo/client evaluation purposes

---

## 12. Non-Functional Requirements

- **Performance**: Full pipeline (ingest + dbt + train) completes in < 5 minutes on standard laptop hardware
- **Reproducibility**: Same input data + same code = same model AUC (random_state=42 set everywhere)
- **Portability**: Pipeline runs on Windows, macOS, Linux without modification
- **Data Quality**: 100% of dbt data quality tests must pass before model training
- **Documentation**: Every module has inline docstrings; every dbt model has a description comment

---

## 13. References & Resources

- [IEEE-CIS Fraud Detection Competition](https://www.kaggle.com/c/ieee-fraud-detection)
- [DuckDB Documentation](https://duckdb.org/docs/)
- [dbt Documentation](https://docs.getdbt.com/)
- [XGBoost Docs — scale_pos_weight](https://xgboost.readthedocs.io/en/stable/parameter.html)
- [MLflow Tracking Guide](https://mlflow.org/docs/latest/tracking.html)
- [Streamlit Documentation](https://docs.streamlit.io/)
