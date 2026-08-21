import time, logging, asyncio
from fastapi import FastAPI, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from prometheus_client import Counter, Histogram, make_asgi_app

from fraud_spike.config import settings
from fraud_spike.domain.schemas import TransactionIn, ScoreResponse, ExplanationItem, ThresholdUpdate
from fraud_spike.domain.exceptions import FraudSpikeError
from fraud_spike.serving.dependencies import get_model, get_manifest, get_velocity_store, get_redis
from fraud_spike.features.explain import build_explainer, explain_transaction

logger = logging.getLogger(settings.service_name)
app = FastAPI(title="Fraud Spike Detector", version="2.0")
app.mount("/metrics", make_asgi_app())

REQUEST_COUNT = Counter("fraud_spike_requests_total", "Scoring requests", ["flagged"])
LATENCY = Histogram("fraud_spike_scoring_latency_seconds", "Scoring latency")

@app.exception_handler(FraudSpikeError)
async def domain_error_handler(request: Request, exc: FraudSpikeError):
    logger.error("domain_error", extra={"error": str(exc), "path": str(request.url.path)})
    raise HTTPException(status_code=422, detail=str(exc))

@app.post("/v1/score", response_model=ScoreResponse)
async def score(
    txn: TransactionIn,
    model=Depends(get_model),
    manifest=Depends(get_manifest),
    store=Depends(get_velocity_store),
):
    start = time.perf_counter()
    uid = txn.uid_key()
    velocity = await store.get_features(uid, now_ts=txn.transaction_dt)
    row = {**txn.raw_features, **velocity, "TransactionAmt": txn.transaction_amt}

    threshold = settings.score_threshold_override or manifest["metrics"].get("threshold", 0.5)
    
    try:
        feature_cols = model.feature_name()
    except Exception:
        feature_cols = list(row.keys())
        
    for col in feature_cols:
        if col not in row:
            row[col] = None
            
    row_filtered = {k: row[k] for k in feature_cols}
    
    proba = float(model.predict([list(row_filtered.values())])[0])
    flagged = proba >= threshold

    reasons: list[ExplanationItem] = []
    if flagged:
        explainer = build_explainer(model)
        reasons = [ExplanationItem(**r) for r in explain_transaction(explainer, feature_cols, row_filtered)]

    await store.record(uid, txn.transaction_dt, txn.transaction_amt)

    LATENCY.observe(time.perf_counter() - start)
    REQUEST_COUNT.labels(flagged=str(flagged)).inc()

    return ScoreResponse(
        transaction_id=txn.transaction_id, fraud_probability=proba, flagged=flagged,
        threshold_used=threshold, reasons=reasons, model_version=manifest["model_version"],
    )

@app.get("/health")
async def health(model=Depends(get_model), manifest=Depends(get_manifest)):
    return {"status": "ok", "model_version": manifest["model_version"]}

@app.post("/v1/threshold")
async def update_threshold(update: ThresholdUpdate):
    settings.score_threshold_override = update.threshold
    return {"status": "ok", "threshold": settings.score_threshold_override}

@app.get("/v1/threshold")
async def get_threshold(manifest=Depends(get_manifest)):
    return {"threshold": settings.score_threshold_override or manifest["metrics"].get("threshold", 0.5)}

@app.websocket("/ws/feed")
async def websocket_feed(websocket: WebSocket):
    await websocket.accept()
    r = await get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe("flagged_channel")
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await websocket.send_text(message["data"])
    except WebSocketDisconnect:
        await pubsub.unsubscribe("flagged_channel")
