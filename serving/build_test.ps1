# Script to build and test the Docker image on Windows

Write-Host "=== Building Docker image ==="
docker build -t sentiment-api:test .

Write-Host "`n=== Testing Docker image ==="

# Create a temporary directory for test model
$TestDir = New-Item -ItemType Directory -Path "$env:TEMP\test-model-$(Get-Date -Format 'yyyyMMddHHmmss')"
Write-Host "Test directory: $TestDir"

# Create a simple test model structure
$ModelDir = New-Item -ItemType Directory -Path "$TestDir\model"

# Create manifest.json
@'
{
    "model_name": "test.model",
    "model_version": "1",
    "model_alias": "champion",
    "source_run_id": "test-run-123",
    "files": []
}
'@ | Set-Content -Path "$ModelDir\manifest.json"

# Create a simple MLmodel file
@'
flavors:
  python_function:
    env:
      conda: conda.yaml
      virtualenv: python_env.yaml
    loader_module: mlflow.sklearn
    model_path: model.pkl
    python_version: "3.12"
artifacts:
  model.pkl: {}
'@ | Set-Content -Path "$ModelDir\MLmodel"

# Create a simple model file
"test" | Set-Content -Path "$ModelDir\model.pkl"

# Copy test model into current directory for Docker build
Copy-Item -Path "$ModelDir" -Destination "." -Recurse

Write-Host "`n=== Running container ==="
docker run -d --name sentiment-test -p 8000:8000 sentiment-api:test

Write-Host "Waiting for container to start..."
Start-Sleep -Seconds 5

Write-Host "`n=== Testing API endpoints ==="

# Test health endpoint
Write-Host "Testing /health endpoint:"
try {
    $health = Invoke-RestMethod -Uri "http://localhost:8000/health" -ErrorAction Stop
    Write-Host "Response: $(ConvertTo-Json $health -Compress)"
} catch {
    Write-Host "Health check failed: $_"
}

# Test model info endpoint
Write-Host "`nTesting /model-info endpoint:"
try {
    $modelInfo = Invoke-RestMethod -Uri "http://localhost:8000/model-info" -ErrorAction Stop
    Write-Host "Response: $(ConvertTo-Json $modelInfo -Compress)"
} catch {
    Write-Host "Model info failed: $_"
}

# Test predict endpoint
Write-Host "`nTesting /predict endpoint:"
try {
    $predict = Invoke-RestMethod -Uri "http://localhost:8000/predict" -Method Post `
        -Headers @{"Content-Type" = "application/json"} `
        -Body '{"texts": ["good movie", "bad movie"]}' -ErrorAction Stop
    Write-Host "Response: $(ConvertTo-Json $predict -Compress)"
} catch {
    Write-Host "Predict failed: $_"
}

Write-Host "`n=== Cleaning up ==="
docker stop sentiment-test
docker rm sentiment-test
docker rmi sentiment-api:test
Remove-Item -Path "model" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path $TestDir -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "`n=== Test completed ==="