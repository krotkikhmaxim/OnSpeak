-- SpeakUP seed data: 500 sessions for ML training
CREATE TABLE IF NOT EXISTS students (
    student_id   SERIAL PRIMARY KEY,
    cefr_level   VARCHAR(2)  NOT NULL,
    topic        VARCHAR(50),
    accent_pref  VARCHAR(20)
);
CREATE TABLE IF NOT EXISTS tutors (
    tutor_id       SERIAL PRIMARY KEY,
    specialization VARCHAR(50),
    rating         FLOAT DEFAULT 4.5,
    availability   FLOAT DEFAULT 1.0
);
CREATE TABLE IF NOT EXISTS sessions (
    session_id  SERIAL PRIMARY KEY,
    student_id  INTEGER REFERENCES students(student_id),
    tutor_id    INTEGER REFERENCES tutors(tutor_id),
    rebook      SMALLINT DEFAULT 0,
    created_at  TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS feature_store (
    student_id          INTEGER,
    tutor_id            INTEGER,
    cefr_match          FLOAT,
    topic_match         FLOAT,
    accent_match        FLOAT,
    tutor_rating        FLOAT,
    avg_rebook_rate     FLOAT,
    student_session_cnt INTEGER,
    computed_at         TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (student_id, tutor_id)
);

INSERT INTO students (cefr_level, topic, accent_pref) VALUES
  ('B1','business','american'),('B2','travel','british'),('A2','daily','any'),
  ('C1','academic','british'),('B1','tech','american'),('A1','daily','any'),
  ('B2','business','american'),('C2','academic','british'),('B1','travel','any'),
  ('A2','daily','american'),('B2','tech','british'),('B1','business','any'),
  ('C1','travel','american'),('A2','daily','british'),('B2','academic','any'),
  ('B1','tech','american'),('A1','daily','british'),('C2','business','american'),
  ('B2','travel','any'),('B1','academic','british');

INSERT INTO tutors (specialization, rating, availability) VALUES
  ('business',4.9,0.8),('travel',4.7,0.9),('daily',4.5,1.0),
  ('academic',4.8,0.7),('tech',4.6,0.85),('daily',4.3,1.0),
  ('business',4.7,0.6),('academic',4.9,0.75),('travel',4.4,0.95),
  ('tech',4.8,0.8);

INSERT INTO sessions (student_id, tutor_id, rebook, created_at)
SELECT
    (random()*19+1)::int,
    (random()*9+1)::int,
    CASE WHEN random() < 0.30 THEN 1 ELSE 0 END,
    NOW() - (random()*180 || ' days')::interval
FROM generate_series(1, 500);
