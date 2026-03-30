---
language:
  - en
license: apache-2.0
tags:
  - fraud-detection
  - fintech
  - tabular
  - classification
  - xgboost
  - dbt
  - duckdb
task_categories:
  - tabular-classification
task_ids:
  - binary-classification
size_categories:
  - 100K<n<1M
---

# IEEE-CIS Fraud Detection — Model-Ready Feature Dataset

## Dataset Summary

This dataset contains **590,540 financial transactions** from the IEEE-CIS Fraud Detection competition, processed through a production-grade data pipeline into a clean, labeled, model-ready feature table.

The pipeline adds 16 engineered features on top of the original IEEE-CIS columns — including card-level velocity, email domain risk rates, and amount anomaly ratios — ready for direct use in fraud detection model training.

**This is the output of the pipeline described in [fintech-fraud-pipeline](https://github.com/Kshitijbhatt1998/fintech-fraud-pipeline).**

## Dataset Details

| Property | Value |
|----------|-------|
| Rows | 590,540 |
| Features | 58 |
| Label column | `is_fraud` (binary: 0 = legit, 1 = fraud) |
| Fraud rate | ~3.5% |
| Date range | ~6 months (Nov 2017 – May 2018) |
| Delivery format | Parquet |

## Supported Tasks

**Binary classification** — predicting whether a financial transaction is fraudulent.

Suitable for training and benchmarking: gradient boosting models (XGBoost, LightGBM), neural networks, or anomaly detection systems.

## Data Source

Original data: [IEEE-CIS Fraud Detection](https://www.kaggle.com/c/ieee-fraud-detection) (Kaggle, 2019).  
All features are anonymized per the original dataset terms. Transaction patterns reflect real e-commerce payment events.

## Dataset Structure

### Feature Groups

**Temporal**
- `transaction_ts` — parsed UTC timestamp
- `hour_of_day` — 0–23
- `day_of_week` — 0–6 (Monday = 0)

**Transaction**
- `transaction_amt` — transaction amount in USD
- `log_amt` — log-transformed amount (ln(amt + 1))
- `product_cd` — product category (W / H / C / S / R)

**Card**
- `card1` – `card6` — card metadata (issuer, type, network)

**Identity**
- `has_identity` — 1 if device fingerprint record exists
- `id_01` – `id_20` — device and browser identity features
- `device_type` — mobile or desktop

**Behavioral (C-features)**
- `C1` – `C14` — counting features (e.g. addresses, payment methods linked to card)

**Time-delta (D-features)**
- `D1` – `D15` — days since various reference events

**Match flags (M-features)**
- `M1_enc` – `M9_enc` — encoded boolean match indicators (0/1)

**Engineered — Card Velocity**
- `card1_txn_count` — total transactions on this card number
- `card1_avg_amt` — historical average transaction amount for this card
- `card1_historical_fraud_rate` — prior fraud rate for this card number

**Engineered — Email Risk**
- `email_txn_count` — total transactions from this email domain
- `email_historical_fraud_rate` — prior fraud rate for this email domain

**Engineered — Anomaly Signals**
- `amt_vs_card_avg_ratio` — current amount ÷ card's historical average
- `is_high_risk_product` — 1 if product_cd = 'W' (highest-fraud product category)

**Label**
- `is_fraud` — 0 = legitimate, 1 = fraudulent

### Data Splits

The dataset does **not** include a predefined train/test split. For time-series-safe evaluation, sort by `transaction_ts` and use a temporal holdout (e.g. last 20%) rather than random split.

## Pipeline

Built with:
- **DuckDB** — columnar in-process ingestion and storage
- **dbt** — SQL-based transformation layer (staging → marts)
- **Python** — feature engineering, null handling, timestamp parsing

Full pipeline code: [github.com/Kshitijbhatt1998/fintech-fraud-pipeline](https://github.com/Kshitijbhatt1998/fintech-fraud-pipeline)

## Benchmark

A baseline XGBoost model trained on this feature set achieves:

| Metric | Score |
|--------|-------|
| CV AUC (5-fold time-series) | **0.9791** |
| Holdout AUC (last 20% of data) | **0.9791** |
| CV Average Precision | see training logs |

Training code: `src/train.py` in the linked repository.

## Licensing and Usage

The underlying data is from the Kaggle IEEE-CIS competition. The pipeline code and engineered features are released under Apache 2.0.

This dataset card and the pipeline are provided as a **public proof-of-work case study** demonstrating custom data pipeline development for fintech AI teams.

## Citation

```
@misc{bhatt2024-fraud-pipeline,
  author = {Bhatt, Kshitij},
  title = {IEEE-CIS Fraud Detection: Model-Ready Feature Dataset},
  year = {2024},
  url = {https://github.com/Kshitijbhatt1998/fintech-fraud-pipeline}
}
```

## Dataset Card Author

**Kshitij Bhatt** — Data Engineer specializing in fintech AI infrastructure and custom data pipelines.

[GitHub](https://github.com/Kshitijbhatt1998) | [LinkedIn](https://linkedin.com/in/kshitijbhatt)
