import subprocess
import threading
import os
import json
from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse

router = APIRouter()

KG_STATUS_FILE = "/app/data/kg_refresh_status.json"

# Helper to run a script and update status
def run_kg_refresh():
    status = {"progress": 0, "stage": "Starting..."}
    with open(KG_STATUS_FILE, "w") as f:
        json.dump(status, f)
    try:
        status["stage"] = "Repopulating Knowledge Graph"
        with open(KG_STATUS_FILE, "w") as f:
            json.dump(status, f)
        subprocess.run(["python", "-m", "app.maintenance.repopulate_kg"], check=True)
        status["progress"] = 50
        status["stage"] = "Building Knowledge Communities"
        with open(KG_STATUS_FILE, "w") as f:
            json.dump(status, f)
        subprocess.run(["python", "-m", "app.maintenance.build_communities"], check=True)
        status["progress"] = 100
        status["stage"] = "Done"
        with open(KG_STATUS_FILE, "w") as f:
            json.dump(status, f)
    except Exception as e:
        status["stage"] = f"Error: {str(e)}"
        with open(KG_STATUS_FILE, "w") as f:
            json.dump(status, f)

@router.post("/kg-refresh/trigger")
def trigger_kg_refresh(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_kg_refresh)
    return {"status": "started"}

@router.get("/kg-refresh/status")
def kg_refresh_status():
    if not os.path.exists(KG_STATUS_FILE):
        return {"progress": 0, "stage": "Not started"}
    with open(KG_STATUS_FILE, "r") as f:
        return json.load(f)
