-- fraud_features (incremental)
-- Drop-in replacement for dbt_project/models/marts/fraud_features.sql
--
-- First run:       builds full table identical to current implementation
-- Subsequent runs: appends only rows where transaction_dt > last known max
--
-- Commands:
--   Normal run:   dbt run --select fraud_features
--   Full rebuild: dbt run --full-refresh --select fraud_features



-- Card velocity: computed over FULL history every run so rates stay current
-- NOTE: Point-in-time correctness requires windowed aggregation in production.
-- See DATA_PIPELINE.md § Production Note for implementation guidance.
WITH card_stats AS (
    SELECT
        card1,
        COUNT(*)                              AS card1_txn_count,
        AVG(transaction_amt)                  AS card1_avg_amt,
        AVG(CAST(is_fraud AS DOUBLE))         AS card1_fraud_rate
    FROM "fraud"."main"."stg_transactions"
    GROUP BY card1
),

email_stats AS (
    SELECT
        purchaser_email_domain,
        COUNT(*)                              AS email_txn_count,
        AVG(CAST(is_fraud AS DOUBLE))         AS email_fraud_rate
    FROM "fraud"."main"."stg_transactions"
    WHERE purchaser_email_domain IS NOT NULL
    GROUP BY purchaser_email_domain
),

-- Only the NEW transactions — the incremental filter
-- On full-refresh or first run, is_incremental() = false → all rows processed
new_transactions AS (
    SELECT * FROM "fraud"."main"."stg_transactions"

    
    WHERE transaction_dt > (SELECT MAX(transaction_dt) FROM "fraud"."main"."fraud_features")
    
)

SELECT
    t.transaction_id,
    t.transaction_dt,
    t.transaction_ts,
    t.transaction_amt,
    t.log_amt,
    t.hour_of_day,
    t.day_of_week,
    t.product_cd,
    t.has_identity,
    t.is_fraud,
    t.card1, t.card2, t.card3, t.card4, t.card5, t.card6,
    t.addr1, t.addr2, t.dist1, t.dist2,
    t.purchaser_email_domain,
    t.recipient_email_domain,
    t.C1, t.C2, t.C3, t.C4, t.C5, t.C6, t.C7, t.C8,
    t.C9, t.C10, t.C11, t.C12, t.C13, t.C14,
    t.D1, t.D2, t.D3, t.D4, t.D5, t.D10, t.D11, t.D15,
    t.M1_enc, t.M2_enc, t.M3_enc, t.M4_enc, t.M5_enc,
    t.M6_enc, t.M7_enc, t.M8_enc, t.M9_enc,
    i.id_01, i.id_02, i.id_03, i.id_05, i.id_06,
    i.id_09, i.id_11, i.id_13, i.id_17, i.id_19, i.id_20,
    i.device_type,
    cs.card1_txn_count,
    cs.card1_avg_amt,
    cs.card1_fraud_rate                       AS card1_historical_fraud_rate,
    es.email_txn_count,
    es.email_fraud_rate                       AS email_historical_fraud_rate,
    CASE WHEN t.product_cd = 'W' THEN 1 ELSE 0 END AS is_high_risk_product,
    CASE
        WHEN cs.card1_avg_amt > 0 THEN t.transaction_amt / cs.card1_avg_amt
        ELSE NULL
    END AS amt_vs_card_avg_ratio

FROM new_transactions t
LEFT JOIN "fraud"."main"."stg_identity" i
    ON t.transaction_id = i.transaction_id
LEFT JOIN card_stats cs
    ON t.card1 = cs.card1
LEFT JOIN email_stats es
    ON t.purchaser_email_domain = es.purchaser_email_domain