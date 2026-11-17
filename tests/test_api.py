"""Test FastAPI model serving API."""
import hashlib
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest
from fastapi.testclient import TestClient

# Import just the app without executing its top-level code
from serving.app import app, verify_model_integrity

# Mock data for testing
MOCK_MANIFEST = {
    "model_name": "test.model",
    "model_version": "1",
    "model_alias": "champion",
    "source_run_id": "test-run-123",
    "files": []
}

class MockModel:
    """Mock MLflow model for testing."""
    def predict(self, data: pd.DataFrame):
        # Return mock predictions: 1 for positive words, 0 otherwise
        return [1 if "good" in text.lower() else 0 for text in data["text"]]

@pytest.fixture
def mock_model():
    """Mock the MLflow model."""
    with patch("serving.app.mlflow.pyfunc.load_model") as mock_load:
        mock_model = MockModel()
        mock_load.return_value = mock_model
        yield mock_model

@pytest.fixture
def test_client(mock_model):
    """Create a test client with mocked model."""
    # Mock the lifespan startup
    with (
        patch("serving.app.verify_model_integrity") as mock_verify,
        patch("serving.app.MODEL_DIR", Path(".")),
        patch("serving.app.MANIFEST_PATH", Path(".") / "manifest.json")
    ):
        mock_verify.return_value = MOCK_MANIFEST
        # Create test client
        with TestClient(app) as client:
            # Manually set app state for testing
            client.app.state.model = mock_model
            client.app.state.manifest = MOCK_MANIFEST
            yield client

def test_health_check(test_client):
    """Test health endpoint."""
    response = test_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["model_loaded"] == True

def test_model_info(test_client):
    """Test model info endpoint."""
    response = test_client.get("/model-info")
    assert response.status_code == 200
    data = response.json()
    assert data["model_name"] == "test.model"
    assert data["model_version"] == "1"
    assert data["model_alias"] == "champion"

def test_predict(test_client):
    """Test prediction endpoint."""
    response = test_client.post(
        "/predict",
        json={"texts": ["good movie", "bad movie"]}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["predictions"] == [1, 0]
    assert data["model_version"] == "1"

def test_predict_validation(test_client):
    """Test input validation."""
    # Empty texts
    response = test_client.post("/predict", json={"texts": []})
    assert response.status_code == 422
    
    # Text too long
    long_text = "x" * 1001
    response = test_client.post("/predict", json={"texts": [long_text]})
    assert response.status_code == 422
    
    # Too many texts
    many_texts = ["text"] * 101
    response = test_client.post("/predict", json={"texts": many_texts})
    assert response.status_code == 422

def test_process_time_header(test_client):
    """Test that X-Process-Time-Ms header is added."""
    response = test_client.get("/health")
    assert "X-Process-Time-Ms" in response.headers
    assert float(response.headers["X-Process-Time-Ms"]) >= 0

def test_tampered_file_rejection():
    """Test that tampered files cause container to fail startup."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        manifest_path = tmp_path / "manifest.json"
        model_dir = tmp_path / "model"
        model_dir.mkdir()
        
        # Create a test file
        test_file = model_dir / "test.txt"
        test_file.write_text("original content")
        
        # Create manifest
        manifest = {
            "model_name": "test",
            "model_version": "1",
            "model_alias": "champion",
            "source_run_id": "test",
            "files": [{
                "path": "test.txt",
                "sha256": hashlib.sha256(b"original content").hexdigest()
            }]
        }
        
        with open(manifest_path, "w") as f:
            json.dump(manifest, f)
        
        # Tamper with file
        test_file.write_text("tampered content")
        
        # Verify should fail
        with patch("serving.app.MANIFEST_PATH", manifest_path), patch("serving.app.MODEL_DIR", tmp_path):
            with pytest.raises(SystemExit):
                verify_model_integrity()

def test_extra_file_rejection():
    """Test that extra files cause container to fail startup."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        manifest_path = tmp_path / "manifest.json"
        model_dir = tmp_path / "model"
        model_dir.mkdir()
        
        # Create manifest with one file
        manifest = {
            "model_name": "test",
            "model_version": "1",
            "model_alias": "champion",
            "source_run_id": "test",
            "files": [{
                "path": "allowed.txt",
                "sha256": hashlib.sha256(b"content").hexdigest()
            }]
        }
        
        with open(manifest_path, "w") as f:
            json.dump(manifest, f)
        
        # Create both files
        allowed_file = model_dir / "allowed.txt"
        allowed_file.write_text("content")
        
        extra_file = model_dir / "extra.txt"
        extra_file.write_text("extra content")
        
        # Verify should fail
        with patch("serving.app.MANIFEST_PATH", manifest_path), patch("serving.app.MODEL_DIR", tmp_path):
            with pytest.raises(SystemExit):
                verify_model_integrity()