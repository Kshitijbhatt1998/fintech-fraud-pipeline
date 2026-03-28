-- fraud_summary: pre-aggregated stats for the Streamlit dashboard
-- Refreshed by running: dbt run --select fraud_summary

WITH base AS (
    SELECT * FROM "fraud"."main"."fraud_features"
)

-- Daily summary
SELECT
    'daily'                             AS grain,
    CAST(transaction_ts AS DATE)        AS dim_value,
    COUNT(*)                            AS txn_count,
    SUM(transaction_amt)                AS total_amt,
    SUM(is_fraud)                       AS fraud_count,
    AVG(CAST(is_fraud AS DOUBLE)) * 100 AS fraud_rate_pct,
    SUM(CASE WHEN is_fraud = 1 THEN transaction_amt ELSE 0 END) AS fraud_amt
FROM base
GROUP BY CAST(transaction_ts AS DATE)

UNION ALL

-- By product
SELECT
    'product'       AS grain,
    product_cd      AS dim_value,
    COUNT(*)        AS txn_count,
    SUM(transaction_amt) AS total_amt,
    SUM(is_fraud)   AS fraud_count,
    AVG(CAST(is_fraud AS DOUBLE)) * 100 AS fraud_rate_pct,
    SUM(CASE WHEN is_fraud = 1 THEN transaction_amt ELSE 0 END) AS fraud_amt
FROM base
GROUP BY product_cd

UNION ALL

-- By card type
SELECT
    'card_type'     AS grain,
    card6           AS dim_value,
    COUNT(*)        AS txn_count,
    SUM(transaction_amt) AS total_amt,
    SUM(is_fraud)   AS fraud_count,
    AVG(CAST(is_fraud AS DOUBLE)) * 100 AS fraud_rate_pct,
    SUM(CASE WHEN is_fraud = 1 THEN transaction_amt ELSE 0 END) AS fraud_amt
FROM base
WHERE card6 IS NOT NULL
GROUP BY card6

UNION ALL

-- By email domain (top 20 by volume)
SELECT
    'email_domain'          AS grain,
    purchaser_email_domain  AS dim_value,
    COUNT(*)                AS txn_count,
    SUM(transaction_amt)    AS total_amt,
    SUM(is_fraud)           AS fraud_count,
    AVG(CAST(is_fraud AS DOUBLE)) * 100 AS fraud_rate_pct,
    SUM(CASE WHEN is_fraud = 1 THEN transaction_amt ELSE 0 END) AS fraud_amt
FROM base
WHERE purchaser_email_domain IS NOT NULL
GROUP BY purchaser_email_domain
QUALIFY ROW_NUMBER() OVER (ORDER BY COUNT(*) DESC) <= 20

UNION ALL

-- By hour of day
SELECT
    'hour_of_day'                       AS grain,
    CAST(hour_of_day AS VARCHAR)        AS dim_value,
    COUNT(*)                            AS txn_count,
    SUM(transaction_amt)                AS total_amt,
    SUM(is_fraud)                       AS fraud_count,
    AVG(CAST(is_fraud AS DOUBLE)) * 100 AS fraud_rate_pct,
    SUM(CASE WHEN is_fraud = 1 THEN transaction_amt ELSE 0 END) AS fraud_amt
FROM base
GROUP BY hour_of_day