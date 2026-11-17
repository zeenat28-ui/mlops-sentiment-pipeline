"""
FastAPI app serving sentiment classifier model.
Fail-closed: container won't start if model files are tampered with.
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
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

# Constants
MODEL_DIR = Path("model")
MANIFEST_PATH = MODEL_DIR / "manifest.json"

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic models
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
    """Verify all model files against manifest."""
    if not MANIFEST_PATH.exists():
        logger.error(f"Manifest not found: {MANIFEST_PATH}")
        sys.exit(1)

    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)

    logger.info(f"Verifying model: {manifest['model_name']} "
                f"version {manifest['model_version']} alias {manifest['model_alias']}")

    for file_info in manifest["files"]:
        file_path = MODEL_DIR / file_info["path"]
        if not file_path.exists():
            logger.error(f"Missing file: {file_path}")
            sys.exit(1)

        with open(file_path, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()

        if file_hash != file_info["sha256"]:
            logger.error(f"Hash mismatch for {file_path}: "
                         f"expected {file_info['sha256'][:16]}..., got {file_hash[:16]}...")
            sys.exit(1)

        logger.debug(f"✓ {file_path} verified")

    # Check for extra files not in manifest
    all_files = {p.relative_to(MODEL_DIR) for p in MODEL_DIR.rglob("*") if p.is_file() and p.resolve() != MANIFEST_PATH.resolve()}
    manifest_files = {Path(info["path"]) for info in manifest["files"]}
    extra_files = all_files - manifest_files

    if extra_files:
        logger.error(f"Extra files found in model directory: {extra_files}")
        sys.exit(1)

    logger.info("✓ Model integrity verified")
    return manifest

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load model on startup."""
    # Verify and load model
    manifest = verify_model_integrity()
    try:
        import mlflow.sklearn
        app.state.model = mlflow.sklearn.load_model(str(MODEL_DIR))
    except Exception:
        app.state.model = mlflow.pyfunc.load_model(str(MODEL_DIR))
    app.state.manifest = manifest
    logger.info(f"Model loaded: {manifest['model_name']} v{manifest['model_version']}")
    yield
    # Cleanup on shutdown if needed
    app.state.model = None
    app.state.manifest = None

# FastAPI app with lifespan
app = FastAPI(
    title="Sentiment Classifier API",
    description="Predict sentiment (1=positive, 0=negative) for text inputs",
    version="1.0.0",
    lifespan=lifespan
)

# Middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000
    response.headers["X-Process-Time-Ms"] = str(round(process_time, 2))
    return response

# Routes
@app.get("/health")
async def health_check(request: Request):
    """Health check endpoint."""
    model_loaded = request.app.state.model is not None
    return {"status": "healthy" if model_loaded else "unhealthy", "model_loaded": model_loaded}

@app.get("/model-info")
async def model_info(request: Request) -> ModelInfoResponse:
    """Get model metadata."""
    manifest = request.app.state.manifest
    return ModelInfoResponse(
        model_name=manifest["model_name"],
        model_version=manifest["model_version"],
        model_alias=manifest["model_alias"],
        source_run_id=manifest["source_run_id"],
        manifest_hash=hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()[:16]
    )

@app.post("/predict", response_model=PredictResponse)
async def predict(request: PredictRequest, http_request: Request):
    """
    Predict sentiment for texts.
    
    Returns predictions: 1=positive, 0=negative.
    """
    try:
        model = http_request.app.state.model
        if model is None:
            raise HTTPException(status_code=503, detail="Model not loaded")
        
        manifest = http_request.app.state.manifest
        
        # Prepare input DataFrame (same format as Databricks smoke test)
        input_df = pd.DataFrame({"text": request.texts})
        
        # Predict
        predictions = model.predict(input_df)
        
        # Convert to int (ensure 0/1)
        predictions = [int(pred) for pred in predictions]
        
        return PredictResponse(
            predictions=predictions,
            model_version=manifest["model_version"],
            model_alias=manifest["model_alias"]
        )
        
    except Exception as e:
        logger.exception(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail="Prediction failed")

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )