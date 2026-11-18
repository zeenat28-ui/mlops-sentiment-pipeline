"""
FastAPI app serving sentiment classifier model.
Fail-closed: container won't start if model files are tampered with.
Exposes Prometheus /metrics for Argo Rollouts canary analysis and SLO monitoring.
"""
import hashlib
import json
import logging
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

import mlflow.pyfunc
import pandas as pd
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, Field, field_validator

MODEL_DIR = Path("model")
MANIFEST_PATH = MODEL_DIR / "manifest.json"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Prometheus Metrics
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)
PREDICTION_LATENCY = Histogram(
    "prediction_latency_seconds",
    "Model inference latency in seconds",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)
PREDICTIONS_TOTAL = Counter(
    "sentiment_predictions_total",
    "Total predictions by sentiment class",
    ["sentiment", "model_version"],
)

class PredictRequest(BaseModel):
    texts: list[str] = Field(..., min_length=1, max_length=100)

    @field_validator("texts")
    @classmethod
    def validate_texts(cls, texts: list[str]) -> list[str]:
        if not texts:
            raise ValueError("texts cannot be empty")
        if len(texts) > 100:
            raise ValueError("Maximum 100 texts allowed")
        for text in texts:
            if not text.strip():
                raise ValueError("Text cannot be empty or whitespace")
            if len(text) > 1000:
                raise ValueError(f"Text too long: {len(text)} > 1000 chars")
        return texts

class PredictResponse(BaseModel):
    model_config = {"protected_namespaces": ()}
    predictions: list[int]
    model_version: str
    model_alias: str

class ModelInfoResponse(BaseModel):
    model_config = {"protected_namespaces": ()}
    model_name: str
    model_version: str
    model_alias: str
    source_run_id: str
    manifest_hash: str

def verify_model_integrity() -> dict:
    if not MANIFEST_PATH.exists():
        logger.error(f"Manifest not found: {MANIFEST_PATH}")
        sys.exit(1)

    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)

    logger.info(
        f"Verifying model: {manifest['model_name']} "
        f"version {manifest['model_version']} alias {manifest['model_alias']}"
    )

    for file_info in manifest["files"]:
        file_path = MODEL_DIR / file_info["path"]
        if not file_path.exists():
            logger.error(f"Missing file: {file_path}")
            sys.exit(1)

        with open(file_path, "rb") as f:
            content = f.read()

        raw_hash = hashlib.sha256(content).hexdigest()
        lf_hash = hashlib.sha256(content.replace(b"\r\n", b"\n")).hexdigest()
        crlf_hash = hashlib.sha256(content.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")).hexdigest()
        if file_info["sha256"] not in {raw_hash, lf_hash, crlf_hash}:
            logger.error(f"Hash mismatch for {file_path}")
            sys.exit(1)

    all_files = {
        p.relative_to(MODEL_DIR)
        for p in MODEL_DIR.rglob("*")
        if p.is_file() and p.resolve() != MANIFEST_PATH.resolve()
    }
    manifest_files = {Path(info["path"]) for info in manifest["files"]}
    extra_files = all_files - manifest_files
    if extra_files:
        logger.error(f"Extra files found in model directory: {extra_files}")
        sys.exit(1)

    logger.info("✓ Model integrity verified")
    return manifest

@asynccontextmanager
async def lifespan(app: FastAPI):
    manifest = verify_model_integrity()
    try:
        import mlflow.sklearn
        app.state.model = mlflow.sklearn.load_model(str(MODEL_DIR))
    except Exception:
        app.state.model = mlflow.pyfunc.load_model(str(MODEL_DIR))
    app.state.manifest = manifest
    logger.info(f"Model loaded: {manifest['model_name']} v{manifest['model_version']}")
    yield
    app.state.model = None
    app.state.manifest = None

app = FastAPI(
    title="Sentiment Classifier API",
    description="Predict sentiment (1=positive, 0=negative) for text inputs",
    version="1.1.0",
    lifespan=lifespan,
)

@app.middleware("http")
async def metrics_and_timing_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time_ms = (time.time() - start_time) * 1000
    response.headers["X-Process-Time-Ms"] = str(round(process_time_ms, 2))
    if request.url.path != "/metrics":
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status_code=str(response.status_code),
        ).inc()
    return response

@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")

@app.get("/health")
async def health_check(request: Request):
    model_loaded = getattr(request.app.state, "model", None) is not None
    if not model_loaded:
        return JSONResponse(status_code=503, content={"status": "unhealthy", "model_loaded": False})
    return {"status": "healthy", "model_loaded": True}

@app.get("/metrics", include_in_schema=False)
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/model-info")
async def model_info(request: Request) -> ModelInfoResponse:
    manifest = request.app.state.manifest
    return ModelInfoResponse(
        model_name=manifest["model_name"],
        model_version=manifest["model_version"],
        model_alias=manifest["model_alias"],
        source_run_id=manifest["source_run_id"],
        manifest_hash=hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()[:16],
    )

@app.post("/predict", response_model=PredictResponse)
async def predict(request: PredictRequest, http_request: Request):
    try:
        model = http_request.app.state.model
        if model is None:
            raise HTTPException(status_code=503, detail="Model not loaded")

        manifest = http_request.app.state.manifest
        input_df = pd.DataFrame({"text": request.texts})

        with PREDICTION_LATENCY.time():
            raw_preds = model.predict(input_df)

        predictions = [int(pred) for pred in raw_preds]
        for pred in predictions:
            PREDICTIONS_TOTAL.labels(
                sentiment="positive" if pred == 1 else "negative",
                model_version=str(manifest["model_version"]),
            ).inc()

        return PredictResponse(
            predictions=predictions,
            model_version=manifest["model_version"],
            model_alias=manifest["model_alias"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail="Prediction failed")
