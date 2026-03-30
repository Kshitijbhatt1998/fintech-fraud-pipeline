# Fintech Fraud Detection Pipeline

**A production-grade data pipeline for fintech AI teams — from raw transaction logs to clean, labeled, model-ready datasets. Built for your model, maintained monthly.**

[![Python](https://img.shields.io/badge/Python-3.10-blue)](https://python.org)
[![dbt](https://img.shields.io/badge/dbt-1.x-orange)](https://getdbt.com)
[![DuckDB](https://img.shields.io/badge/DuckDB-0.10-yellow)](https://duckdb.org)
[![XGBoost AUC](https://img.shields.io/badge/XGBoost%20AUC-0.9791-brightgreen)](./models/)
[![Streamlit](https://img.shields.io/badge/Dashboard-Streamlit-red)](./src/dashboard.py)
[![Huggingface]([(https://huggingface.co/datasets/Kshitijbhatt1998/ieee-fraud-detection-pipeline-features)](./src/dashboard.py)
---

## What This Demonstrates

This pipeline ingests, cleans, transforms, and delivers **590,540 real financial transactions** as a model-ready feature dataset — the same kind of pipeline I build for fintech AI teams as a custom service.

**If you're building a fraud detection, credit scoring, or AML model and need clean, structured training data — this is the type of pipeline I deliver.**

→ [Book a discovery call](https://calendly.com) | [Connect on LinkedIn](https://linkedin.com/in/kshitijbhatt)

---

## Pipeline Results

| Metric | Value |
|--------|-------|
| Raw transactions ingested | 590,540 |
| Identity records joined | 144,233 |
| Features engineered | 58 |
| Model (XGBoost) CV AUC | **0.9791** |
| Model Holdout AUC | **0.9791** |
| Fraud rate in dataset | ~3.5% |
| Pipeline runtime (full) | < 4 minutes |

---

## Architecture

```
Raw CSVs (Kaggle IEEE-CIS)
        │
        ▼
[1. Ingest]  src/ingest_data.py
        DuckDB ← read_csv_auto
        - raw_transactions (590,540 rows)
        - raw_identity (144,233 rows)
        - Drop >90% null columns
        - Engineer: transaction_ts, hour_of_day, log_amt, M-flag encoding
        │
        ▼
[2. Transform]  dbt (dbt_project/)
        staging/
          stg_transactions  ← clean_transactions (view)
          stg_identity      ← clean_identity (view)
        marts/
          fraud_features    ← joined + velocity features (table)
          fraud_summary     ← aggregated risk by product/card/email (table)
        │
        ▼
[3. Train]  src/train.py
        XGBoost + TimeSeriesSplit (5-fold)
        MLflow experiment tracking
        → models/xgb_fraud_v1.pkl
        │
        ▼
[4. Serve]  src/dashboard.py
        Streamlit: Overview / Risk Breakdown / Model Performance / Transaction Explorer
```

---

## Engineered Features

Beyond raw columns, this pipeline adds:

| Feature | Logic |
|---------|-------|
| `card1_txn_count` | Transaction velocity per card |
| `card1_avg_amt` | Historical average transaction amount per card |
| `card1_historical_fraud_rate` | Card-level prior fraud rate |
| `email_txn_count` | Transaction count per email domain |
| `email_historical_fraud_rate` | Domain-level prior fraud rate |
| `is_high_risk_product` | Binary flag for product code W |
| `amt_vs_card_avg_ratio` | Amount relative to card's historical average |
| `log_amt` | Log-transformed transaction amount |
| `hour_of_day` / `day_of_week` | Temporal features from raw timestamp |
| `has_identity` | Whether a device/browser identity record exists |

---

## Tech Stack

| Layer | Tool |
|-------|------|
| Storage | DuckDB |
| Transformation | dbt (staging → marts, Medallion pattern) |
| ML | XGBoost, scikit-learn |
| Experiment tracking | MLflow |
| Dashboard | Streamlit + Plotly |
| Language | Python 3.10 |

---

## Quickstart

```bash
# 1. Clone and install
git clone https://github.com/Kshitijbhatt1998/fintech-fraud-pipeline.git
cd fintech-fraud-pipeline
pip install -r requirements.txt

# 2. Download data
# Place Kaggle IEEE-CIS files into data/raw/
# https://www.kaggle.com/c/ieee-fraud-detection/data

# 3. Ingest
python src/ingest_data.py

# 4. Transform (dbt)
cd dbt_project && dbt run && dbt test && cd ..

# 5. Train model
python src/train.py

# 6. Launch dashboard
streamlit run src/dashboard.py
```

---

## Data Source

IEEE-CIS Fraud Detection dataset (Kaggle, 2019). Publicly available for research and ML development.  
Transaction data represents real e-commerce payment events with anonymized features.


