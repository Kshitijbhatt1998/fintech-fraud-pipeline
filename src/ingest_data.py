import duckdb
import pandas as pd
import time
from pathlib import Path
import os

# Project paths
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "fraud.duckdb"
RAW_PATH = BASE_DIR / "data" / "raw"

def main():
    print(f"Connecting to {DB_PATH}...")
    # Ensure data directory exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        os.remove(DB_PATH)
    con = duckdb.connect(str(DB_PATH))

    # --- 1. Ingest Raw CSVs ---
    print("Ingesting raw transactions...")
    t0 = time.time()
    con.execute(f"CREATE OR REPLACE TABLE raw_transactions AS SELECT * FROM read_csv_auto('{RAW_PATH}/train_transaction.csv', header=true)")
    n_tx = con.execute("SELECT COUNT(*) FROM raw_transactions").fetchone()[0]
    print(f"  Loaded {n_tx:,} rows into raw_transactions ({(time.time()-t0):.1f}s)")

    print("Ingesting raw identity...")
    t0 = time.time()
    con.execute(f"CREATE OR REPLACE TABLE raw_identity AS SELECT * FROM read_csv_auto('{RAW_PATH}/train_identity.csv', header=true)")
    n_id = con.execute("SELECT COUNT(*) FROM raw_identity").fetchone()[0]
    print(f"  Loaded {n_id:,} rows into raw_identity ({(time.time()-t0):.1f}s)")

    # --- 2. Clean Data ---
    print("Cleaning transactions...")
    # Identify columns with > 90% nulls
    cols_df = con.execute("DESCRIBE raw_transactions").df()
    all_cols = cols_df['column_name'].tolist()
    
    # Calculate null % efficiently
    null_exprs = ", ".join([f"ROUND(COUNT(*) FILTER (WHERE \"{c}\" IS NULL) * 100.0 / COUNT(*), 2) AS \"{c}\"" for c in all_cols])
    null_df = con.execute(f"SELECT {null_exprs} FROM raw_transactions").df()
    null_series = null_df.iloc[0]
    
    THRESHOLD = 90.0
    cols_to_drop = null_series[null_series > THRESHOLD].index.tolist()
    cols_to_keep = [c for c in all_cols if c not in cols_to_drop]
    keep_cols_sql = ", ".join([f'"{c}"' for c in cols_to_keep])

    # Reference epoch from notebook
    BASE_DT_EPOCH = int(pd.Timestamp('2017-11-30').timestamp())

    con.execute(f"""
        CREATE OR REPLACE TABLE clean_transactions AS
        SELECT
            {keep_cols_sql},
            epoch_ms(CAST(TransactionDT + {BASE_DT_EPOCH} AS BIGINT) * 1000) AS transaction_ts,
            hour(epoch_ms(CAST(TransactionDT + {BASE_DT_EPOCH} AS BIGINT) * 1000)) AS hour_of_day,
            dayofweek(epoch_ms(CAST(TransactionDT + {BASE_DT_EPOCH} AS BIGINT) * 1000)) AS day_of_week,
            ln(TransactionAmt + 1) AS log_amt,
            CASE WHEN TransactionID IN (SELECT TransactionID FROM raw_identity) THEN 1 ELSE 0 END AS has_identity,
            CASE WHEN M1 = 'T' THEN 1 WHEN M1 = 'F' THEN 0 ELSE NULL END AS M1_enc,
            CASE WHEN M2 = 'T' THEN 1 WHEN M2 = 'F' THEN 0 ELSE NULL END AS M2_enc,
            CASE WHEN M3 = 'T' THEN 1 WHEN M3 = 'F' THEN 0 ELSE NULL END AS M3_enc,
            CASE WHEN M4 = 'M0' THEN 0 WHEN M4 = 'M1' THEN 1 WHEN M4 = 'M2' THEN 2 ELSE NULL END AS M4_enc,
            CASE WHEN M5 = 'T' THEN 1 WHEN M5 = 'F' THEN 0 ELSE NULL END AS M5_enc,
            CASE WHEN M6 = 'T' THEN 1 WHEN M6 = 'F' THEN 0 ELSE NULL END AS M6_enc,
            CASE WHEN M7 = 'T' THEN 1 WHEN M7 = 'F' THEN 0 ELSE NULL END AS M7_enc,
            CASE WHEN M8 = 'T' THEN 1 WHEN M8 = 'F' THEN 0 ELSE NULL END AS M8_enc,
            CASE WHEN M9 = 'T' THEN 1 WHEN M9 = 'F' THEN 0 ELSE NULL END AS M9_enc
        FROM raw_transactions
    """)
    n_clean = con.execute("SELECT COUNT(*) FROM clean_transactions").fetchone()[0]
    print(f"  Created clean_transactions: {n_clean:,} rows")

    print("Cleaning identity...")
    con.execute("CREATE OR REPLACE TABLE clean_identity AS SELECT * FROM raw_identity")
    n_id_clean = con.execute("SELECT COUNT(*) FROM clean_identity").fetchone()[0]
    print(f"  Created clean_identity: {n_id_clean:,} rows")

    con.close()
    print("Ingestion complete.")

if __name__ == "__main__":
    main()
