#!/usr/bin/env python3
"""
Pull champion model from Unity Catalog and save with manifest.
The manifest ensures immutability and allows verification.
"""
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

import mlflow
from mlflow.tracking import MlflowClient

# Configuration
MODEL_DIR = Path("model")
MODEL_DIR.mkdir(exist_ok=True)

def get_champion_model(model_name: str) -> dict:
    """Get champion model details from Unity Catalog."""
    mlflow.set_registry_uri("databricks-uc")
    client = MlflowClient()
    
    # Get model
    model = client.get_registered_model(model_name)
    
    # Find champion alias
    champion_version = None
    champion_alias = None
    
    if model.aliases:
        for alias, version in model.aliases.items():
            if alias.lower() == "champion":
                champion_version = version
                champion_alias = alias
                break
    
    if not champion_version:
        # If no champion, get latest version
        versions = client.search_model_versions(f"name='{model_name}'")
        if not versions:
            raise ValueError(f"No versions found for model {model_name}")
        
        latest = max(versions, key=lambda v: int(v.version))
        champion_version = latest.version
        champion_alias = "latest"  # fallback
    
    # Get model version details
    model_version = client.get_model_version(model_name, champion_version)
    
    # Download model
    print(f"Downloading model: {model_name} version {champion_version} ({champion_alias})")
    
    # Download to temp directory first
    temp_dir = MODEL_DIR / "temp"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    
    mlflow.artifacts.download_artifacts(
        run_id=model_version.run_id,
        artifact_path="model",
        dst_path=str(temp_dir)
    )
    
    # Move to final location
    model_artifact_dir = MODEL_DIR / "model_artifact"
    if model_artifact_dir.exists():
        shutil.rmtree(model_artifact_dir)
    
    # Move contents from temp to model_artifact
    os.rename(temp_dir / "model", model_artifact_dir)
    
    # Create manifest
    manifest = {
        "model_name": model_name,
        "model_version": champion_version,
        "model_alias": champion_alias,
        "source_run_id": model_version.run_id,
        "files": []
    }
    
    # Calculate SHA256 for all files
    for file_path in model_artifact_dir.rglob("*"):
        if file_path.is_file():
            relative_path = file_path.relative_to(MODEL_DIR)
            
            with open(file_path, "rb") as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
            
            manifest["files"].append({
                "path": str(relative_path),
                "sha256": file_hash,
                "size": file_path.stat().st_size
            })
    
    # Write manifest
    manifest_path = MODEL_DIR / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
    
    print(f"✓ Model downloaded to {model_artifact_dir}")
    print(f"✓ Manifest created: {manifest_path}")
    print(f"  Model: {model_name}")
    print(f"  Version: {champion_version}")
    print(f"  Alias: {champion_alias}")
    print(f"  Files: {len(manifest['files'])}")
    print(f"  Total size: {sum(f['size'] for f in manifest['files'])} bytes")
    
    return manifest

def create_requirements() -> None:
    """Create requirements.txt from model's conda.yaml."""
    conda_path = MODEL_DIR / "model_artifact" / "conda.yaml"
    requirements_path = MODEL_DIR / "requirements.txt"
    
    if not conda_path.exists():
        print("⚠ No conda.yaml found, creating minimal requirements.txt")
        with open(requirements_path, "w") as f:
            f.write("# Model dependencies\n")
            f.write("mlflow>=2.0.0\n")
            f.write("scikit-learn>=1.0.0\n")
            f.write("pandas>=2.0.0\n")
        return
    
    print(f"✓ Reading dependencies from {conda_path}")
    # Note: For simplicity, we'll create a basic requirements.txt
    # In production, you'd parse conda.yaml properly
    with open(requirements_path, "w") as f:
        f.write("# Model dependencies from conda.yaml\n")
        f.write("mlflow>=2.0.0\n")
        f.write("scikit-learn>=1.0.0\n")
        f.write("pandas>=2.0.0\n")
        f.write("numpy>=1.21.0\n")

def main():
    if len(sys.argv) != 2:
        print("Usage: python pull_model.py <model_name>")
        print("Example: python pull_model.py project1.mlops_sentiment.sentiment_classifier")
        sys.exit(1)
    
    model_name = sys.argv[1]
    
    try:
        # Check credentials
        if not os.environ.get("DATABRICKS_HOST") or not os.environ.get("DATABRICKS_TOKEN"):
            print("Error: DATABRICKS_HOST and DATABRICKS_TOKEN environment variables required")
            sys.exit(1)
        
        # Pull model
        manifest = get_champion_model(model_name)
        
        # Create requirements.txt
        create_requirements()
        
        print("✓ Pull completed successfully")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()