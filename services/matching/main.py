"""SpeakUP Matching API — FastAPI + Prometheus + MLflow fallback"""
import time, os, logging
from contextlib import asynccontextmanager
import mlflow, mlflow.lightgbm, numpy as np, pandas as pd
import psycopg2, redis as redis_lib
from fastapi import FastAPI, HTTPException
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from pydantic import BaseModel
from starlette.responses import Response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REQUEST_COUNT   = Counter("speakup_requests_total", "Total requests", ["endpoint", "status"])
REQUEST_LATENCY = Histogram("speakup_request_duration_seconds", "Latency", ["endpoint"],
                            buckets=[.05,.1,.25,.5,.75,1,2,5])
MODEL_VERSION   = Gauge("speakup_model_version", "Current model version")
MATCH_SCORE     = Histogram("speakup_match_score", "Match scores",
                            buckets=[0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0])

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://speakup:speakup@localhost:5432/speakup")
REDIS_URL    = os.getenv("REDIS_URL",    "redis://localhost:6379")
MLFLOW_URI   = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
MODEL_NAME   = os.getenv("MODEL_NAME",   "speakup-matching")
MODEL_STAGE  = os.getenv("MODEL_STAGE",  "Production")

model = None
redis_client = None

def load_model():
    global model
    try:
        mlflow.set_tracking_uri(MLFLOW_URI)
        model = mlflow.lightgbm.load_model(f"models:/{MODEL_NAME}/{MODEL_STAGE}")
        logger.info("MLflow model loaded"); MODEL_VERSION.set(1)
    except Exception as e:
        logger.warning(f"MLflow unavailable ({e}), using rule-based v0"); model = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client
    try:
        redis_client = redis_lib.from_url(REDIS_URL, decode_responses=True)
    except Exception:
        redis_client = None
    load_model()
    yield
    if redis_client:
        try: redis_client.close()
        except: pass

app = FastAPI(title="SpeakUP Matching API", version="1.0.0", lifespan=lifespan)

CEFR_MAP = {"A1":1,"A2":2,"B1":3,"B2":4,"C1":5,"C2":6}

class MatchRequest(BaseModel):
    student_id: int

class TutorMatch(BaseModel):
    tutor_id: int; score: float; specialization: str; rating: float

class MatchResponse(BaseModel):
    student_id: int; matches: list[TutorMatch]
    model_version: str; latency_ms: float

def get_conn(): return psycopg2.connect(DATABASE_URL)

def get_student(sid: int) -> dict:
    if redis_client:
        c = redis_client.hgetall(f"student:{sid}")
        if c: return c
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT student_id,cefr_level,topic,accent_pref FROM students WHERE student_id=%s",(sid,))
    row = cur.fetchone(); conn.close()
    if not row: raise HTTPException(404, f"Student {sid} not found")
    d = {"student_id":row[0],"cefr_level":row[1],"topic":row[2] or "","accent_pref":row[3] or "any"}
    if redis_client:
        redis_client.hset(f"student:{sid}", mapping=d)
        redis_client.expire(f"student:{sid}", 3600)
    return d

def get_tutors() -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql("SELECT tutor_id,specialization,rating,availability FROM tutors WHERE availability>0.1", conn)
    conn.close(); return df

def build_features(student: dict, tutors: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame([{
        "student_cefr":  CEFR_MAP.get(str(student.get("cefr_level","B1")),3),
        "topic_match":   1.0 if student.get("topic")==t["specialization"] else 0.0,
        "accent_match":  1.0 if student.get("accent_pref","any")=="any" else 0.8,
        "tutor_rating":  float(t["rating"]),
        "availability":  float(t["availability"]),
    } for _,t in tutors.iterrows()])

def rule_score(student: dict, tutors: pd.DataFrame) -> np.ndarray:
    scores = []
    for _,t in tutors.iterrows():
        s = float(t["rating"])/5.0
        if student.get("topic")==t["specialization"]: s += 0.3
        if student.get("accent_pref","any")=="any": s += 0.1
        s += float(t["availability"])*0.1
        scores.append(min(s,1.0))
    return np.array(scores)

@app.get("/health")
def health():
    return {"status":"ok","model":"mlflow" if model else "rule-based-v0"}

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type="text/plain; version=0.0.4; charset=utf-8")

@app.post("/match", response_model=MatchResponse)
def match(req: MatchRequest):
    t0 = time.perf_counter()
    try:
        student = get_student(req.student_id)
        tutors  = get_tutors()
        if tutors.empty: raise HTTPException(503, "No tutors available")
        features = build_features(student, tutors)
        if model is not None:
            scores = model.predict(features); mv = "lightgbm-v1"
        else:
            scores = rule_score(student, tutors); mv = "rule-based-v0"
        tutors = tutors.copy(); tutors["score"] = scores
        top3 = tutors.nlargest(3,"score")
        matches = []
        for _,row in top3.iterrows():
            MATCH_SCORE.observe(float(row["score"]))
            matches.append(TutorMatch(tutor_id=int(row["tutor_id"]),score=round(float(row["score"]),4),
                                      specialization=str(row["specialization"]),rating=float(row["rating"])))
        ms = (time.perf_counter()-t0)*1000
        REQUEST_LATENCY.labels(endpoint="/match").observe(ms/1000)
        REQUEST_COUNT.labels(endpoint="/match",status="200").inc()
        return MatchResponse(student_id=req.student_id,matches=matches,model_version=mv,latency_ms=round(ms,2))
    except HTTPException:
        REQUEST_COUNT.labels(endpoint="/match",status="4xx").inc(); raise
    except Exception as e:
        REQUEST_COUNT.labels(endpoint="/match",status="500").inc()
        raise HTTPException(500, str(e))
