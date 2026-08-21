from functools import lru_cache
import json
import lightgbm as lgb
import redis.asyncio as aioredis
from pathlib import Path

from fraud_spike.config import settings
from fraud_spike.features.online import OnlineVelocityStore, OnlineNetworkStore
from fraud_spike.domain.exceptions import ModelNotLoadedError
import joblib

@lru_cache
def get_model() -> lgb.Booster:
    try:
        return lgb.Booster(model_file=settings.model_path)
    except Exception as exc:
        raise ModelNotLoadedError(str(exc)) from exc

@lru_cache
def get_iso_model():
    try:
        return joblib.load('models/fraud_spike_isoforest.joblib')
    except Exception as exc:
        raise ModelNotLoadedError(str(exc)) from exc

@lru_cache
def get_manifest() -> dict:
    try:
        return json.loads(Path(settings.model_manifest_path).read_text())
    except FileNotFoundError:
        return {"model_version": "unknown", "metrics": {"threshold": 0.5}}

_redis_client: aioredis.Redis | None = None

async def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client

async def get_velocity_store() -> OnlineVelocityStore:
    return OnlineVelocityStore(await get_redis(), settings.velocity_windows_seconds)

async def get_network_store() -> OnlineNetworkStore:
    return OnlineNetworkStore(await get_redis(), (3600,))
