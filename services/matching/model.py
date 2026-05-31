"""LightGBM training + MLflow registry for SpeakUP matching."""
import os, mlflow, mlflow.lightgbm, lightgbm as lgb, numpy as np, psycopg2
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score
from features import build_training_features, FEATURE_COLS

DATABASE_URL   = os.getenv("DATABASE_URL","postgresql://speakup:speakup@localhost:5432/speakup")
MLFLOW_URI     = os.getenv("MLFLOW_TRACKING_URI","http://localhost:5000")
MODEL_NAME     = os.getenv("MODEL_NAME","speakup-matching")
NDCG_THRESHOLD = float(os.getenv("NDCG_THRESHOLD","0.70"))
AUC_THRESHOLD  = float(os.getenv("AUC_THRESHOLD","0.65"))

def ndcg_at_k(y_true, y_score, k=3):
    order = np.argsort(y_score)[::-1]
    yt = np.take(y_true, order[:k])
    gains = 2**yt - 1
    disc  = np.log2(np.arange(2, len(gains)+2))
    dcg   = np.sum(gains/disc)
    ideal = np.sort(y_true)[::-1][:k]
    idcg  = np.sum((2**ideal-1)/disc[:len(ideal)])
    return dcg/idcg if idcg>0 else 0.0

def train_and_register():
    mlflow.set_tracking_uri(MLFLOW_URI)
    mlflow.set_experiment("speakup-matching")
    conn = psycopg2.connect(DATABASE_URL)
    df   = build_training_features(conn); conn.close()
    if len(df)<100: raise ValueError(f"Not enough data: {len(df)}")
    X = df[FEATURE_COLS]; y = df["target"]
    X_tr,X_te,y_tr,y_te = train_test_split(X,y,test_size=0.2,random_state=42)
    params = {"objective":"binary","metric":["binary_logloss","auc"],
              "num_leaves":31,"learning_rate":0.05,"n_estimators":200,"random_state":42,"verbose":-1}
    with mlflow.start_run() as run:
        mlflow.log_params(params)
        mdl = lgb.LGBMClassifier(**params)
        mdl.fit(X_tr,y_tr,eval_set=[(X_te,y_te)],callbacks=[lgb.early_stopping(20,verbose=False)])
        preds = mdl.predict_proba(X_te)[:,1]
        auc   = roc_auc_score(y_te,preds)
        ndcg3 = float(np.mean([ndcg_at_k(y_te.values[np.random.choice(len(y_te),min(10,len(y_te)),replace=False)],
                                          preds[np.random.choice(len(preds),min(10,len(preds)),replace=False)]) for _ in range(50)]))
        mlflow.log_metric("roc_auc",round(auc,4)); mlflow.log_metric("ndcg_at_3",round(ndcg3,4))
        info = mlflow.lightgbm.log_model(mdl,"model",registered_model_name=MODEL_NAME)
        run_id = run.info.run_id
    return {"run_id":run_id,"roc_auc":auc,"ndcg_at_3":ndcg3,
            "passed":auc>=AUC_THRESHOLD and ndcg3>=NDCG_THRESHOLD,"model_uri":info.model_uri}

if __name__=="__main__":
    r = train_and_register(); print(r)
    if not r["passed"]: import sys; sys.exit(1)
