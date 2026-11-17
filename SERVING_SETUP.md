# FastAPI + Docker Model Serving Setup

This guide explains how to serve your Databricks-trained sentiment model outside Databricks using FastAPI and Docker.

## Architecture

```
Databricks Unity Catalog → pull_model.py → model/ → Docker → FastAPI → /predict
```

**Key Features:**
- **Immutable Model**: Model "baked" into Docker image, no runtime token needed
- **Fail-closed**: Container won't start if model files are tampered with
- **Secure**: Non-root user, read-only model directory
- **Production-ready**: Health checks, monitoring headers, input validation

## Quick Start

### 1. Pull Model from Databricks

```powershell
# Set credentials (temporary, only in this session)
$env:DATABRICKS_HOST = "https://your-workspace.cloud.databricks.com"
$env:DATABRICKS_TOKEN = "<your-databricks-token>"

# Pull champion model
python serving/pull_model.py project1.mlops_sentiment.sentiment_classifier
```

This will:
- Download champion model from Unity Catalog
- Save to `model/` directory
- Create `manifest.json` with SHA256 hashes
- Extract dependencies to `model/requirements.txt`

### 2. Check Model Dependencies

```powershell
# Check extracted dependencies
Get-Content model/requirements.txt
```

If there are Databricks-specific packages, they may need adjustment.

### 3. Build Docker Image

```powershell
docker build -f serving/Dockerfile -t mlops-sentiment-api:latest .
```

### 4. Run Container

```powershell
docker run --rm -p 8000:8000 mlops-sentiment-api:latest
```

### 5. Test API

```powershell
# Health check
Invoke-RestMethod http://localhost:8000/health

# Model info
Invoke-RestMethod http://localhost:8000/model-info

# Prediction
$body = @{
    texts = @("great movie, loved it", "terrible, waste of time")
} | ConvertTo-Json

Invoke-RestMethod -Uri http://localhost:8000/predict -Method Post -ContentType "application/json" -Body $body
```

**Expected output:**
```json
{
  "predictions": [1, 0],
  "model_version": "1",
  "model_alias": "champion"
}
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/model-info` | GET | Model metadata (name, version, alias) |
| `/predict` | POST | Predict sentiment for texts |

**Predict Request:**
```json
{
  "texts": ["text1", "text2", ...]
}
```

**Predict Response:**
```json
{
  "predictions": [1, 0, ...],
  "model_version": "1",
  "model_alias": "champion"
}
```

## Security Features

1. **Immutable Model**: Model files verified against SHA256 manifest
2. **Tamper Detection**: Extra/missing/modified files prevent startup
3. **Non-root User**: Container runs as user `appuser` (uid 10001)
4. **Read-only Model**: Model directory mounted read-only
5. **Input Validation**: Text length and batch size limits
6. **No Secrets**: No Databricks tokens in image

## Development

### Run Tests
```powershell
pytest tests/test_api.py -v
```

### Local Development
```powershell
# Install dependencies
pip install -r serving/requirements-api.txt

# Run locally (for testing without Docker)
uvicorn serving.app:app --reload --port 8000
```

## CI/CD Integration

The model serving is integrated into the CI pipeline:

1. **CI Tests**: API tests run in GitHub Actions
2. **Linting**: `ruff check serving` included in CI
3. **Make Commands**: New commands in Makefile:
   - `make pull-model`
   - `make docker-build`
   - `make docker-run`

## Troubleshooting

### Common Issues

1. **Build fails with package conflicts**
   - Check `model/requirements.txt` for Databricks-specific packages
   - Adjust `requirements-api.txt` if needed

2. **Model fails to load**
   - Check MLflow model format compatibility
   - Verify Python version matches training environment

3. **Container won't start**
   - Check manifest verification errors
   - Verify file permissions

4. **Predictions differ from Databricks**
   - Ensure same input format (DataFrame with "text" column)
   - Check model version/alias matches

## Next Steps

1. **Add to CI**: Automated Docker build and push to registry
2. **Security Scanning**: Add Trivy scan for vulnerabilities
3. **Monitoring**: Add Prometheus metrics
4. **Deployment**: Helm chart for Kubernetes deployment

## Notes

- The champion alias is used by default
- Model is immutable once pulled (requires rebuild for new version)
- No authentication/rate limiting in this basic version
- Logs are minimal for security (no text logging)