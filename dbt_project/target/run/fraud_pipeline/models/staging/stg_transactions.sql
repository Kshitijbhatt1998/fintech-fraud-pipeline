
  
  create view "fraud"."main"."stg_transactions__dbt_tmp" as (
    -- stg_transactions: clean view of raw transaction data
-- Selects from clean_transactions (built in 02_data_pipeline.ipynb)
-- Renames columns to snake_case standards, casts types

SELECT
    TransactionID       AS transaction_id,
    TransactionDT       AS transaction_dt,
    transaction_ts,
    TransactionAmt      AS transaction_amt,
    log_amt,
    hour_of_day,
    day_of_week,
    ProductCD           AS product_cd,
    has_identity,
    isFraud             AS is_fraud,

    -- Card features
    card1, card2, card3, card4, card5, card6,

    -- Address and distance
    addr1, addr2,
    dist1, dist2,

    -- Email domains
    P_emaildomain       AS purchaser_email_domain,
    R_emaildomain       AS recipient_email_domain,

    -- C features (counting/behavioral)
    C1, C2, C3, C4, C5, C6, C7, C8, C9, C10, C11, C12, C13, C14,

    -- D features (time-delta/distance)
    D1, D2, D3, D4, D5, D6, D7, D8, D9, D10, D11, D12, D13, D14, D15,

    -- M features (encoded)
    M1_enc, M2_enc, M3_enc, M4_enc, M5_enc, M6_enc, M7_enc, M8_enc, M9_enc

FROM "fraud"."main"."clean_transactions"
  );
