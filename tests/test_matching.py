"""SpeakUP API Tests"""
import pytest, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__),"../services/matching"))
os.environ.setdefault("DATABASE_URL","postgresql://speakup:speakup@localhost:5432/speakup")
os.environ.setdefault("REDIS_URL","redis://localhost:6379")
os.environ.setdefault("MLFLOW_TRACKING_URI","http://localhost:5000")
os.environ.setdefault("MODEL_NAME","speakup-matching")
os.environ.setdefault("MODEL_STAGE","Production")
from fastapi.testclient import TestClient
from main import app
client = TestClient(app)

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_metrics():
    r = client.get("/metrics")
    assert r.status_code == 200

def test_match_valid():
    r = client.post("/match", json={"student_id": 1})
    assert r.status_code in (200, 404, 503)
    if r.status_code == 200:
        d = r.json()
        assert "matches" in d
        assert len(d["matches"]) <= 3

def test_match_invalid():
    r = client.post("/match", json={"student_id": 999999})
    assert r.status_code in (404, 503)

def test_match_latency():
    import time
    t = time.perf_counter()
    client.post("/match", json={"student_id": 1})
    assert (time.perf_counter()-t)*1000 < 5000
