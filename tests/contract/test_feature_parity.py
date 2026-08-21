"""Proves offline (training) and online (serving) velocity features agree
on an identical event sequence. If this fails, the model is scoring on
features it was never trained to see — that's a silent correctness bug,
not a crash, which is what makes it dangerous."""

import fakeredis
import pandas as pd
import pytest

from fraud_spike.features.offline import add_velocity_features, build_uid
from fraud_spike.features.online import OnlineVelocityStore

@pytest.mark.asyncio
async def test_offline_online_parity():
    events = [
        {"card1": 1, "card2": 1, "card3": 1, "card5": 1, "addr1": 1, "TransactionDT": 0, "TransactionAmt": 10.0},
        {"card1": 1, "card2": 1, "card3": 1, "card5": 1, "addr1": 1, "TransactionDT": 300, "TransactionAmt": 1.0},
        {"card1": 1, "card2": 1, "card3": 1, "card5": 1, "addr1": 1, "TransactionDT": 1800, "TransactionAmt": 1.5},
        {"card1": 1, "card2": 1, "card3": 1, "card5": 1, "addr1": 1, "TransactionDT": 4000, "TransactionAmt": 200.0},
    ]

    df = pd.DataFrame(events)
    df = build_uid(df)
    df = add_velocity_features(df, windows=[('3600s', '3600s')])

    fake_redis = fakeredis.FakeAsyncRedis(decode_responses=True)
    store = OnlineVelocityStore(fake_redis, windows_seconds=(3600,))
    uid = df["uid"].iloc[0]

    online_counts = []
    for event in events:
        feats = await store.get_features(uid, now_ts=event["TransactionDT"])
        online_counts.append(feats["uid_txn_count_3600s"])
        await store.record(uid, event["TransactionDT"], event["TransactionAmt"])

    assert list(df["uid_txn_count_3600s"]) == online_counts
