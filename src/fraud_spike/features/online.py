from __future__ import annotations
import uuid
import redis.asyncio as aioredis

class OnlineVelocityStore:
    """Serve-time equivalent of the pandas rolling-window features in
    features/offline.py. Same semantics: count/min-amount over the past
    N seconds for a uid, excluding the event currently being scored."""

    def __init__(self, redis_client: aioredis.Redis, windows_seconds: tuple[int, ...]):
        self._redis = redis_client
        self._windows = windows_seconds
        self._max_window = max(windows_seconds)

    def _key(self, uid: str) -> str:
        return f"velocity:{uid}"

    async def get_features(self, uid: str, now_ts: float) -> dict[str, float]:
        key = self._key(uid)
        features: dict[str, float] = {}
        for window in self._windows:
            entries = await self._redis.zrangebyscore(key, now_ts - window, now_ts)
            amounts = [float(str(e).split(":")[1]) for e in entries]  # client uses decode_responses=True
            features[f"uid_txn_count_{window}s"] = float(len(amounts))
            features[f"uid_amt_min_{window}s"] = min(amounts) if amounts else -1.0
        return features

    async def record(self, uid: str, ts: float, amount: float) -> None:
        key = self._key(uid)
        member = f"{ts}:{amount}:{uuid.uuid4().hex[:8]}"  # suffix avoids same-timestamp collisions
        pipe = self._redis.pipeline()
        pipe.zadd(key, {member: ts})
        pipe.zremrangebyscore(key, 0, ts - self._max_window)  # bounds memory: only keep max-window history
        pipe.expire(key, self._max_window * 2)                # safety net for uids that go permanently quiet
        await pipe.execute()

class OnlineNetworkStore:
    def __init__(self, redis_client: aioredis.Redis, windows_seconds: tuple[int, ...]):
        self._redis = redis_client
        self._windows = windows_seconds
        self._max_window = max(windows_seconds)

    def _key(self, ip: str) -> str:
        return f"network:ip:{ip}:uids"

    async def get_features(self, ip: str | None, now_ts: float) -> dict[str, float]:
        if ip is None or str(ip) == "nan":
            return {f"ip_unique_cards_{w}s": 0.0 for w in self._windows}
            
        key = self._key(str(ip))
        features: dict[str, float] = {}
        for window in self._windows:
            count = await self._redis.zcount(key, now_ts - window, now_ts)
            features[f"ip_unique_cards_{window}s"] = float(count)
        return features

    async def record(self, ip: str | None, uid: str, ts: float) -> None:
        if ip is None or str(ip) == "nan":
            return
        key = self._key(str(ip))
        pipe = self._redis.pipeline()
        pipe.zadd(key, {uid: ts})
        pipe.zremrangebyscore(key, 0, ts - self._max_window)
        pipe.expire(key, self._max_window * 2)
        await pipe.execute()
