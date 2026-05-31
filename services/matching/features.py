"""Feature engineering for SpeakUP matching model."""
import os, pandas as pd, psycopg2

DATABASE_URL = os.getenv("DATABASE_URL","postgresql://speakup:speakup@localhost:5432/speakup")
CEFR_MAP = {"A1":1,"A2":2,"B1":3,"B2":4,"C1":5,"C2":6}
FEATURE_COLS = ["cefr_num","topic_match","accent_match","tutor_rating","availability",
                "avg_rebook_rate_tutor","student_session_count"]

def build_training_features(conn=None) -> pd.DataFrame:
    close = False
    if conn is None:
        conn = psycopg2.connect(DATABASE_URL); close = True
    q = """
    SELECT
        st.cefr_level,
        CASE WHEN st.topic=t.specialization THEN 1.0 ELSE 0.0 END AS topic_match,
        CASE WHEN st.accent_pref='any' THEN 1.0 ELSE 0.8 END AS accent_match,
        t.rating AS tutor_rating, t.availability,
        COALESCE(AVG(s2.rebook) OVER (PARTITION BY s.tutor_id
            ORDER BY s.created_at ROWS BETWEEN 30 PRECEDING AND 1 PRECEDING), 0.3) AS avg_rebook_rate_tutor,
        COUNT(s2.session_id) OVER (PARTITION BY s.student_id ORDER BY s.created_at) AS student_session_count,
        s.rebook AS target
    FROM sessions s
    JOIN students st ON s.student_id=st.student_id
    JOIN tutors t ON s.tutor_id=t.tutor_id
    LEFT JOIN sessions s2 ON s2.tutor_id=s.tutor_id
    ORDER BY s.created_at
    """
    df = pd.read_sql(q, conn)
    if close: conn.close()
    df["cefr_num"] = df["cefr_level"].map(CEFR_MAP).fillna(3)
    df["student_session_count"] = df["student_session_count"].fillna(1)
    return df[FEATURE_COLS + ["target"]]
