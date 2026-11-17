#!/bin/bash
# Script to build and test the Docker image

set -e  # Exit on error

echo "=== Building Docker image ==="
docker build -t sentiment-api:test .

echo -e "\n=== Testing Docker image ==="

# Create a temporary directory for test model
TEST_DIR=$(mktemp -d)
echo "Test directory: $TEST_DIR"

# Create a simple test model structure
mkdir -p "$TEST_DIR/model"
cat > "$TEST_DIR/model/manifest.json" << 'EOF'
{
    "model_name": "test.model",
    "model_version": "1",
    "model_alias": "champion",
    "source_run_id": "test-run-123",
    "files": []
}
EOF

# Create a simple MLmodel file
cat > "$TEST_DIR/model/MLmodel" << 'EOF'
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
EOF

# Create a simple model file
echo "test" > "$TEST_DIR/model/model.pkl"

# Copy test model into current directory for Docker build
cp -r "$TEST_DIR/model" .

echo -e "\n=== Running container ==="
docker run -d --name sentiment-test -p 8000:8000 sentiment-api:test

echo "Waiting for container to start..."
sleep 5

echo -e "\n=== Testing API endpoints ==="

# Test health endpoint
echo "Testing /health endpoint:"
curl -s http://localhost:8000/health | jq . || echo "Health check failed"

# Test model info endpoint
echo -e "\nTesting /model-info endpoint:"
curl -s http://localhost:8000/model-info | jq . || echo "Model info failed"

# Test predict endpoint
echo -e "\nTesting /predict endpoint:"
curl -s -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"texts": ["good movie", "bad movie"]}' | jq . || echo "Predict failed"

echo -e "\n=== Cleaning up ==="
docker stop sentiment-test
docker rm sentiment-test
docker rmi sentiment-api:test
rm -rf model "$TEST_DIR"

echo -e "\n=== Test completed successfully ==="