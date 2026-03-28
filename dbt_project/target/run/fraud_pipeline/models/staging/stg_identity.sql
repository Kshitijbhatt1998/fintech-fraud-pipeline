
  
  create view "fraud"."main"."stg_identity__dbt_tmp" as (
    -- stg_identity: clean view of identity data
-- id_01..id_38 are anonymized device/browser/network features

SELECT
    TransactionID AS transaction_id,

    -- Numeric identity features
    id_01, id_02, id_03, id_04, id_05, id_06, id_07, id_08, id_09, id_10,
    id_11,

    -- Categorical identity features
    id_12, id_13, id_14, id_15, id_16, id_17, id_18, id_19, id_20,
    id_21, id_22, id_23, id_24, id_25, id_26, id_27, id_28, id_29, id_30,
    id_31, id_32, id_33, id_34, id_35, id_36, id_37, id_38,

    -- Device info
    DeviceType  AS device_type,
    DeviceInfo  AS device_info

FROM "fraud"."main"."clean_identity"
  );
