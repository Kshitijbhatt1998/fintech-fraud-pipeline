import duckdb
from huggingface_hub import HfApi

# Step 1: Export Parquet
print("Exporting Parquet...")
con = duckdb.connect('data/fraud.duckdb', read_only=True)
con.execute("COPY fraud_features TO 'fraud_features.parquet' (FORMAT PARQUET)")
count = con.execute('SELECT COUNT(*) FROM fraud_features').fetchone()[0]
con.close()
print(f"Done. Exported {count:,} rows to fraud_features.parquet")

# Step 2: Upload both files
print("Uploading to HuggingFace...")
api = HfApi()

api.upload_file(
    path_or_fileobj='fraud_features.parquet',
    path_in_repo='fraud_features.parquet',
    repo_id='Kshitijbhatt1998/ieee-fraud-detection-pipeline-features',
    repo_type='dataset'
)
print("Parquet uploaded.")

api.upload_file(
    path_or_fileobj='HUGGINGFACE_CARD.md',
    path_in_repo='README.md',
    repo_id='Kshitijbhatt1998/ieee-fraud-detection-pipeline-features',
    repo_type='dataset'
)
print("Dataset card uploaded.")
print("All done. Check huggingface.co/datasets/Kshitijbhatt1998/ieee-fraud-detection-pipeline-features")
