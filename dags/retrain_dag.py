"""SpeakUP Retrain Pipeline DAG — MLOps Level 2"""
from datetime import datetime, timedelta
import os
from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.empty import EmptyOperator

DATABASE_URL   = os.getenv("DATABASE_URL","postgresql://speakup:speakup@postgres:5432/speakup")
MLFLOW_URI     = os.getenv("MLFLOW_TRACKING_URI","http://mlflow:5000")
MIN_ROWS       = int(os.getenv("MIN_TRAINING_ROWS","100"))
NDCG_THRESHOLD = float(os.getenv("NDCG_THRESHOLD","0.70"))
AUC_THRESHOLD  = float(os.getenv("AUC_THRESHOLD","0.65"))

default_args = {"owner":"ml-engineer","retries":1,"retry_delay":timedelta(minutes=5),"email_on_failure":False}

def _check_data(**ctx):
    import psycopg2
    conn = psycopg2.connect(DATABASE_URL); cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM sessions WHERE created_at > NOW() - INTERVAL '7 days'")
    count = cur.fetchone()[0]; conn.close()
    return "feature_engineering" if count >= MIN_ROWS else "skip_retrain"

def _feature_engineering(**ctx):
    import psycopg2, sys
    sys.path.insert(0,"/opt/airflow/services/matching")
    from features import build_training_features
    conn = psycopg2.connect(DATABASE_URL)
    df = build_training_features(conn); conn.close()
    ctx["ti"].xcom_push(key="feature_count", value=len(df))

def _train_model(**ctx):
    import sys, os
    sys.path.insert(0,"/opt/airflow/services/matching")
    os.environ["DATABASE_URL"] = DATABASE_URL
    os.environ["MLFLOW_TRACKING_URI"] = MLFLOW_URI
    from model import train_and_register
    result = train_and_register()
    ctx["ti"].xcom_push(key="train_result", value=result)

def _evaluate_model(**ctx):
    result = ctx["ti"].xcom_pull(task_ids="train_model", key="train_result")
    return "canary_deploy" if result["passed"] else "rollback"

def _canary_deploy(**ctx):
    import redis
    r = redis.from_url(os.getenv("REDIS_URL","redis://redis:6379"))
    result = ctx["ti"].xcom_pull(task_ids="train_model", key="train_result")
    r.set("model:canary:run_id", result["run_id"], ex=3600)
    r.set("model:canary:traffic", "5", ex=3600)
    r.set("model:canary:active", "1", ex=3600)
    print(f"Canary: run_id={result['run_id']}, 5% traffic")

def _guardrail_check(**ctx):
    import psycopg2
    conn = psycopg2.connect(DATABASE_URL); cur = conn.cursor()
    cur.execute("SELECT AVG(rebook) FROM sessions WHERE created_at > NOW() - INTERVAL '1 hour'")
    rate = cur.fetchone()[0] or 0.0; conn.close()
    return "full_deploy" if rate >= 0.20 else "rollback"

def _full_deploy(**ctx):
    import mlflow
    from mlflow.tracking import MlflowClient
    mlflow.set_tracking_uri(MLFLOW_URI)
    client = MlflowClient()
    result = ctx["ti"].xcom_pull(task_ids="train_model", key="train_result")
    for v in client.search_model_versions("name='speakup-matching'"):
        if v.run_id == result["run_id"]:
            client.transition_model_version_stage("speakup-matching", v.version, "Production",
                                                  archive_existing_versions=True)
            print(f"Model v{v.version} → Production"); break

def _rollback(**ctx):
    import redis
    r = redis.from_url(os.getenv("REDIS_URL","redis://redis:6379"))
    r.delete("model:canary:active")
    print("Rollback: canary cleared")

with DAG("speakup_retrain_pipeline", default_args=default_args,
         schedule_interval="0 2 * * *", start_date=datetime(2026,1,1),
         catchup=False, tags=["speakup","mlops","level-2"]) as dag:

    check_data          = BranchPythonOperator(task_id="check_data", python_callable=_check_data)
    skip_retrain        = EmptyOperator(task_id="skip_retrain")
    feature_engineering = PythonOperator(task_id="feature_engineering", python_callable=_feature_engineering)
    train_model         = PythonOperator(task_id="train_model",         python_callable=_train_model)
    evaluate_model      = BranchPythonOperator(task_id="evaluate_model",python_callable=_evaluate_model)
    canary_deploy       = PythonOperator(task_id="canary_deploy",       python_callable=_canary_deploy)
    guardrail_check     = BranchPythonOperator(task_id="guardrail_check",python_callable=_guardrail_check)
    full_deploy         = PythonOperator(task_id="full_deploy",         python_callable=_full_deploy)
    rollback            = PythonOperator(task_id="rollback",            python_callable=_rollback)
    done                = EmptyOperator(task_id="done", trigger_rule="none_failed_min_one_success")

    check_data >> [feature_engineering, skip_retrain]
    feature_engineering >> train_model >> evaluate_model
    evaluate_model >> [canary_deploy, rollback]
    canary_deploy >> guardrail_check
    guardrail_check >> [full_deploy, rollback]
    [full_deploy, rollback, skip_retrain] >> done
