import os
import time
from pathlib import Path

import duckdb
import pandas as pd

from src.monitoring import capture_exception, setup_monitoring

log = setup_monitoring('ingest')

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH  = BASE_DIR / 'data' / 'fraud.duckdb'
RAW_PATH = BASE_DIR / 'data' / 'raw'

# ── Input validation ──────────────────────────────────────────────────────────
_ALLOWED_CSV_NAMES = {'train_transaction.csv', 'train_identity.csv'}


def _safe_csv_path(raw_dir: Path, filename: str) -> str:
    """Resolve CSV path and verify it stays inside raw_dir.

    Prevents path traversal (e.g. filename='../../etc/passwd').
    """
    if filename not in _ALLOWED_CSV_NAMES:
        raise ValueError(f'Unexpected CSV filename: {filename!r}')
    resolved = (raw_dir / filename).resolve()
    if not str(resolved).startswith(str(raw_dir.resolve())):
        raise ValueError(f'Path traversal detected for: {filename!r}')
    if not resolved.exists():
        raise FileNotFoundError(f'CSV not found: {resolved}')
    return str(resolved)


def main():
    log.info('Starting ingestion | db=%s', DB_PATH)

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        os.remove(DB_PATH)
        log.info('Removed existing database')

    con = duckdb.connect(str(DB_PATH))

    try:
        # ── 1. Ingest Raw CSVs ────────────────────────────────────────────────
        tx_path = _safe_csv_path(RAW_PATH, 'train_transaction.csv')
        log.info('Ingesting raw transactions from %s', tx_path)
        t0 = time.time()
        con.execute(
            "CREATE OR REPLACE TABLE raw_transactions AS "
            f"SELECT * FROM read_csv_auto('{tx_path}', header=true)"
        )
        n_tx = con.execute('SELECT COUNT(*) FROM raw_transactions').fetchone()[0]
        log.info('Loaded %d rows into raw_transactions (%.1fs)', n_tx, time.time() - t0)

        id_path = _safe_csv_path(RAW_PATH, 'train_identity.csv')
        log.info('Ingesting raw identity from %s', id_path)
        t0 = time.time()
        con.execute(
            "CREATE OR REPLACE TABLE raw_identity AS "
            f"SELECT * FROM read_csv_auto('{id_path}', header=true)"
        )
        n_id = con.execute('SELECT COUNT(*) FROM raw_identity').fetchone()[0]
        log.info('Loaded %d rows into raw_identity (%.1fs)', n_id, time.time() - t0)

        # ── 2. Clean transactions ─────────────────────────────────────────────
        log.info('Cleaning transactions (dropping >90%% null columns)...')
        cols_df  = con.execute('DESCRIBE raw_transactions').df()
        all_cols = cols_df['column_name'].tolist()

        null_exprs = ', '.join([
            f'ROUND(COUNT(*) FILTER (WHERE "{c}" IS NULL) * 100.0 / COUNT(*), 2) AS "{c}"'
            for c in all_cols
        ])
        null_series = con.execute(f'SELECT {null_exprs} FROM raw_transactions').df().iloc[0]

        THRESHOLD = 90.0
        MANDATORY_COLS = {
            'TransactionID', 'TransactionDT', 'TransactionAmt', 'ProductCD', 'isFraud',
            'card1', 'card2', 'card3', 'card4', 'card5', 'card6',
            'addr1', 'addr2', 'dist1', 'dist2',
            'P_emaildomain', 'R_emaildomain',
            'C1','C2','C3','C4','C5','C6','C7','C8','C9','C10','C11','C12','C13','C14',
            'D1','D2','D3','D4','D5','D6','D7','D8','D9','D10','D11','D12','D13','D14','D15',
        }
        cols_to_drop = [
            c for c in null_series[null_series > THRESHOLD].index.tolist()
            if c not in MANDATORY_COLS
        ]
        cols_to_keep    = [c for c in all_cols if c not in cols_to_drop]
        keep_cols_sql   = ', '.join([f'"{c}"' for c in cols_to_keep])
        BASE_DT_EPOCH   = int(pd.Timestamp('2017-11-30').timestamp())

        log.info('Dropping %d high-null columns, keeping %d', len(cols_to_drop), len(cols_to_keep))

        con.execute(f"""
            CREATE OR REPLACE TABLE clean_transactions AS
            SELECT
                {keep_cols_sql},
                epoch_ms(CAST(TransactionDT + {BASE_DT_EPOCH} AS BIGINT) * 1000) AS transaction_ts,
                hour(epoch_ms(CAST(TransactionDT + {BASE_DT_EPOCH} AS BIGINT) * 1000))     AS hour_of_day,
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
        n_clean = con.execute('SELECT COUNT(*) FROM clean_transactions').fetchone()[0]
        log.info('Created clean_transactions: %d rows', n_clean)

        con.execute('CREATE OR REPLACE TABLE clean_identity AS SELECT * FROM raw_identity')
        n_id_clean = con.execute('SELECT COUNT(*) FROM clean_identity').fetchone()[0]
        log.info('Created clean_identity: %d rows', n_id_clean)

        # ── 3. Database indexes ───────────────────────────────────────────────
        # DuckDB uses zone maps (min/max per column chunk) for OLAP scans
        # automatically. Explicit ART indexes speed up point lookups and
        # selective range queries — most useful on high-cardinality PK columns
        # and the fraud label used in every dashboard filter.
        log.info('Creating database indexes...')
        con.execute("""
            CREATE INDEX IF NOT EXISTS idx_clean_txn_id
                ON clean_transactions (TransactionID)
        """)
        con.execute("""
            CREATE INDEX IF NOT EXISTS idx_clean_txn_fraud
                ON clean_transactions (isFraud)
        """)
        con.execute("""
            CREATE INDEX IF NOT EXISTS idx_clean_txn_ts
                ON clean_transactions (transaction_ts)
        """)
        con.execute("""
            CREATE INDEX IF NOT EXISTS idx_clean_id_txn
                ON clean_identity (TransactionID)
        """)
        log.info('Indexes created')

    except Exception as exc:
        capture_exception(exc, {'stage': 'ingest'})
        log.exception('Ingestion failed')
        raise
    finally:
        con.close()

    log.info('Ingestion complete')


if __name__ == '__main__':
    main()
