import redis, json, time
import pandas as pd
from fraud_spike.config import settings

def replay(csv_path: str, stream='txn_stream', speed_factor=2000):
    r = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    df = pd.read_csv(csv_path)
    df = df.sort_values('TransactionDT').reset_index(drop=True)
    prev_dt = None
    for _, row in df.iterrows():
        if prev_dt is not None:
            gap = (row['TransactionDT'] - prev_dt) / speed_factor
            time.sleep(max(gap, 0))
        payload = row.drop(labels=['isFraud'], errors='ignore').to_dict()
        # Convert any float NaNs to None for JSON
        payload = {k: (None if pd.isna(v) else v) for k, v in payload.items()}
        r.xadd(stream, {'data': json.dumps(payload, default=str)})
        prev_dt = row['TransactionDT']

if __name__ == "__main__":
    print("Replaying historical transactions onto stream...")
    # placeholder for actual data path
    # replay('data/raw/train_transaction.csv')
