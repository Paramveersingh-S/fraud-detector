import pandas as pd

CATEGORICAL_COLS = [
    'ProductCD', 'card4', 'card6', 'P_emaildomain',
    'R_emaildomain', 'DeviceType', 'M1', 'M2', 'M3',
]

def load_and_merge(transaction_path: str, identity_path: str) -> pd.DataFrame:
    txn = pd.read_csv(transaction_path)
    identity = pd.read_csv(identity_path)
    df = txn.merge(identity, on='TransactionID', how='left')
    return df

def build_uid(df: pd.DataFrame) -> pd.DataFrame:
    """A simplified per-card proxy identifier."""
    df = df.copy()
    for col in ['card1', 'card2', 'card3', 'card5', 'addr1']:
        df[col] = df[col].astype('Int64').astype(str)
    df['uid'] = df[['card1', 'card2', 'card3', 'card5', 'addr1']].agg('_'.join, axis=1)
    return df

def add_velocity_features(df: pd.DataFrame, windows=(('1h', '1h'), ('24h', '24h'))) -> pd.DataFrame:
    """Rolling per-uid transaction count and min-amount, using only PAST
    transactions (closed='left') so nothing leaks from the current or
    future row."""
    df = df.sort_values(['uid', 'TransactionDT']).reset_index(drop=True)
    df['_dt'] = pd.to_datetime(df['TransactionDT'], unit='s')
    df = df.set_index('_dt')

    for label, window in windows:
        df[f'uid_txn_count_{label}'] = (
            df.groupby('uid')['TransactionAmt']
              .rolling(window, closed='left')
              .count()
              .reset_index(level=0, drop=True)
        )
        df[f'uid_amt_min_{label}'] = (
            df.groupby('uid')['TransactionAmt']
              .rolling(window, closed='left')
              .min()
              .reset_index(level=0, drop=True)
        )

    df = df.reset_index(drop=True)

    count_cols = [c for c in df.columns if c.startswith('uid_txn_count_')]
    amt_cols = [c for c in df.columns if c.startswith('uid_amt_min_')]
    df[count_cols] = df[count_cols].fillna(0)
    df[amt_cols] = df[amt_cols].fillna(df['TransactionAmt'].median() if len(df) > 0 else 0)

    return df

def prepare_categoricals(df: pd.DataFrame) -> pd.DataFrame:
    for c in CATEGORICAL_COLS:
        if c in df.columns:
            df[c] = df[c].astype('category')
    return df

def add_network_features(df: pd.DataFrame, windows=(('1h', '3600s'),)) -> pd.DataFrame:
    import numpy as np
    df = df.sort_values(['addr1', 'TransactionDT']).reset_index(drop=True)
    df['_dt'] = pd.to_datetime(df['TransactionDT'], unit='s')
    df = df.set_index('_dt')
    
    df['uid_encoded'] = pd.factorize(df['uid'])[0]
    
    for label, window in windows:
        df[f'ip_unique_cards_{label}'] = (
            df.groupby('addr1')['uid_encoded']
              .rolling(window, closed='left')
              .apply(lambda x: len(np.unique(x[~np.isnan(x)])) if len(x) > 0 else 0, raw=True)
              .reset_index(level=0, drop=True)
        )
        
    df = df.reset_index(drop=True)
    count_cols = [c for c in df.columns if c.startswith('ip_unique_cards_')]
    df[count_cols] = df[count_cols].fillna(0)
    df = df.drop(columns=['uid_encoded'])
    return df

def build_features(transaction_path: str, identity_path: str) -> pd.DataFrame:
    df = load_and_merge(transaction_path, identity_path)
    df = build_uid(df)
    df = df.sort_values('TransactionDT').reset_index(drop=True)
    df = add_velocity_features(df)
    df = add_network_features(df)
    df = prepare_categoricals(df)
    return df
