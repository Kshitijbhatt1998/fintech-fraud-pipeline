-- fraud_summary (incremental)
-- Drop-in replacement for dbt_project/models/marts/fraud_summary.sql
--
-- Strategy: DELETE + INSERT on affected date partitions.
-- When new transactions arrive, we recompute summary rows for any
-- dates that appear in the new batch — keeping historical rows intact.




-- Identify which dimension values are affected by the new batch
WITH affected_dates AS (
    SELECT DISTINCT CAST(transaction_ts AS DATE) AS affected_date
    FROM "fraud"."main"."stg_transactions"
    WHERE transaction_dt > (SELECT MAX(CAST(dim_value AS DATE))
                            FROM "fraud"."main"."fraud_summary"
                            WHERE grain = 'daily')
),


base AS (
    SELECT * FROM "fraud"."main"."stg_transactions"
    
    -- Only recompute rows for dates in the new batch
    WHERE CAST(transaction_ts AS DATE) IN (SELECT affected_date FROM affected_dates)
    
)

-- Daily grain
SELECT
    'daily'                                  AS grain,
    CAST(CAST(transaction_ts AS DATE) AS VARCHAR) AS dim_value,
    COUNT(*)                                 AS txn_count,
    SUM(is_fraud)                            AS fraud_count,
    ROUND(AVG(CAST(is_fraud AS DOUBLE)) * 100, 4) AS fraud_rate_pct,
    SUM(transaction_amt)                     AS total_amt,
    SUM(CASE WHEN is_fraud = 1 THEN transaction_amt ELSE 0 END) AS fraud_amt
FROM base
GROUP BY CAST(transaction_ts AS DATE)

UNION ALL

-- Product grain (full recompute — small cardinality)
SELECT
    'product'                                AS grain,
    product_cd                               AS dim_value,
    COUNT(*)                                 AS txn_count,
    SUM(is_fraud)                            AS fraud_count,
    ROUND(AVG(CAST(is_fraud AS DOUBLE)) * 100, 4) AS fraud_rate_pct,
    SUM(transaction_amt)                     AS total_amt,
    SUM(CASE WHEN is_fraud = 1 THEN transaction_amt ELSE 0 END) AS fraud_amt
FROM "fraud"."main"."stg_transactions"
GROUP BY product_cd

UNION ALL

-- Card type grain
SELECT
    'card_type'                              AS grain,
    card6                                    AS dim_value,
    COUNT(*)                                 AS txn_count,
    SUM(is_fraud)                            AS fraud_count,
    ROUND(AVG(CAST(is_fraud AS DOUBLE)) * 100, 4) AS fraud_rate_pct,
    SUM(transaction_amt)                     AS total_amt,
    SUM(CASE WHEN is_fraud = 1 THEN transaction_amt ELSE 0 END) AS fraud_amt
FROM "fraud"."main"."stg_transactions"
GROUP BY card6

UNION ALL

-- Email domain grain (top 50 by volume)
SELECT
    'email_domain'                           AS grain,
    purchaser_email_domain                   AS dim_value,
    COUNT(*)                                 AS txn_count,
    SUM(is_fraud)                            AS fraud_count,
    ROUND(AVG(CAST(is_fraud AS DOUBLE)) * 100, 4) AS fraud_rate_pct,
    SUM(transaction_amt)                     AS total_amt,
    SUM(CASE WHEN is_fraud = 1 THEN transaction_amt ELSE 0 END) AS fraud_amt
FROM "fraud"."main"."stg_transactions"
WHERE purchaser_email_domain IS NOT NULL
GROUP BY purchaser_email_domain
QUALIFY ROW_NUMBER() OVER (ORDER BY COUNT(*) DESC) <= 50

UNION ALL

-- Hour of day grain
SELECT
    'hour_of_day'                            AS grain,
    CAST(hour_of_day AS VARCHAR)             AS dim_value,
    COUNT(*)                                 AS txn_count,
    SUM(is_fraud)                            AS fraud_count,
    ROUND(AVG(CAST(is_fraud AS DOUBLE)) * 100, 4) AS fraud_rate_pct,
    SUM(transaction_amt)                     AS total_amt,
    SUM(CASE WHEN is_fraud = 1 THEN transaction_amt ELSE 0 END) AS fraud_amt
FROM "fraud"."main"."stg_transactions"
GROUP BY hour_of_day