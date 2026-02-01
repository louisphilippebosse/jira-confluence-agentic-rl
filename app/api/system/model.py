"""
Model API - LLM model status and progress endpoints
"""
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
import requests
import os
import json
import glob
import logging

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# Paths for Ollama model storage
BLOBS_PATH = "/root/.ollama/models/blobs/"
MANIFESTS_BASE = "/root/.ollama/models/manifests/registry.ollama.ai/library/"


@router.get("/model-status")
def model_status():
    """Check if the Ollama model is ready to serve requests"""
    try:
        ollama_url = settings.ollama_base_url.rstrip("/")
        model = settings.ollama_model
        resp = requests.get(f"{ollama_url}/api/tags")
        
        if resp.status_code == 200:
            data = resp.json()
            for m in data.get("models", []):
                if m.get("name", "").startswith(model.split(":")[0]):
                    if m.get("size", 0) > 0:
                        return {"ready": True, "status": "Model loaded"}
                    else:
                        return {"ready": False, "status": "Model found but not loaded"}
            return {"ready": False, "status": "Model not found"}
        else:
            return JSONResponse(status_code=503, content={"ready": False, "status": "Ollama not responding"})
    except Exception as e:
        return JSONResponse(status_code=503, content={"ready": False, "status": f"Error: {str(e)}"})


@router.get("/model-progress")
def model_progress(
    model: str = Query(None, description="Model name, e.g. 'llama3'"),
    variant: str = Query(None, description="Model variant/tag, e.g. '8b'"),
):
    """Get model download progress"""
    try:
        manifest_path = None
        used_model = model
        used_variant = variant
        
        if model and variant:
            manifest_path = os.path.join(MANIFESTS_BASE, model, variant)
        else:
            manifest_files = glob.glob(os.path.join(MANIFESTS_BASE, '*', '*'))
            if not manifest_files:
                logger.error(f"No manifest files found in {MANIFESTS_BASE}")
                return JSONResponse(status_code=404, content={"error": "No model manifests found"})
            manifest_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            manifest_path = manifest_files[0]
            parts = manifest_path.split('/')
            if len(parts) >= 2:
                used_model = parts[-2]
                used_variant = parts[-1]
        
        if not os.path.exists(manifest_path):
            logger.error(f"Manifest file not found: {manifest_path}")
            return JSONResponse(status_code=404, content={"error": f"Model manifest not found for {used_model}:{used_variant}"})
        
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
        
        model_layer = next((l for l in manifest["layers"] if l["mediaType"] == "application/vnd.ollama.image.model"), None)
        if not model_layer:
            return JSONResponse(status_code=404, content={"error": "Model layer not found in manifest"})
        
        expected_size = model_layer["size"]
        digest = model_layer["digest"].replace("sha256:", "")
        
        actual_size = 0
        for fname in os.listdir(BLOBS_PATH):
            if digest in fname:
                fpath = os.path.join(BLOBS_PATH, fname)
                actual_size += os.path.getsize(fpath)
        
        percent = min(100, int((actual_size / expected_size) * 100)) if expected_size else 0
        return {"progress": percent, "downloaded": actual_size, "total": expected_size}
        
    except Exception as e:
        logger.error(f"Error in model_progress: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
