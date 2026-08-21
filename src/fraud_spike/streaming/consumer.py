import asyncio
import json
import logging
import redis.asyncio as aioredis
import httpx

from fraud_spike.config import settings

logger = logging.getLogger("fraud_spike.consumer")
MAX_RETRIES = 3

async def consume(stream="txn_stream", group="scorers", consumer_name="scorer-1"):
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        await r.xgroup_create(stream, group, id="0", mkstream=True)
    except aioredis.ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise

    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=2.0) as client:
        while True:
            entries = await r.xreadgroup(group, consumer_name, {stream: ">"}, count=10, block=5000)
            for _, messages in entries:
                for msg_id, fields in messages:
                    await _handle_with_retry(client, r, stream, group, msg_id, fields)

async def _handle_with_retry(client, r, stream, group, msg_id, fields):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            payload = json.loads(fields["data"])
            resp = await client.post("/v1/score", json=payload, timeout=2.0)
            resp.raise_for_status()
            result = resp.json()
            if result["flagged"]:
                flagged_data = {"txn": payload, "score": result["fraud_probability"], "reasons": result["reasons"]}
                payload_str = json.dumps(flagged_data, default=str)
                await r.xadd("flagged_stream", {"data": payload_str})
                await r.publish("flagged_channel", payload_str)
            await r.xack(stream, group, msg_id)
            return
        except Exception as exc:
            logger.warning("scoring_attempt_failed", extra={"msg_id": msg_id, "attempt": attempt, "error": str(exc)})
            if attempt == MAX_RETRIES:
                await r.xadd("dead_letter_stream", {"data": json.dumps(fields), "error": str(exc)})
                await r.xack(stream, group, msg_id)
            else:
                await asyncio.sleep(0.2 * attempt)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(consume())
