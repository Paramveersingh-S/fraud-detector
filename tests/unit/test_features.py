import pandas as pd
from fraud_spike.features.offline import build_uid, add_velocity_features

def test_cold_start_has_zero_velocity():
    df = pd.DataFrame({
        'card1': [1], 'card2': [1], 'card3': [1], 'card5': [1], 'addr1': [1],
        'TransactionDT': [1000], 'TransactionAmt': [50.0],
    })
    df = build_uid(df)
    df = add_velocity_features(df, windows=[('3600s', '3600s')])
    assert df['uid_txn_count_3600s'].iloc[0] == 0

def test_no_lookahead_leakage():
    df = pd.DataFrame({
        'card1': [1, 1], 'card2': [1, 1], 'card3': [1, 1], 'card5': [1, 1], 'addr1': [1, 1],
        'TransactionDT': [1000, 1600], 'TransactionAmt': [5.0, 5.0],
    })
    df = build_uid(df)
    df = add_velocity_features(df, windows=[('3600s', '3600s')])
    df = df.sort_values('TransactionDT')
    assert df['uid_txn_count_3600s'].iloc[0] == 0
    assert df['uid_txn_count_3600s'].iloc[1] == 1
