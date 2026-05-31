
# ML-манифест OnSpeak — Уровень зрелости 2 (MLOps Level 2)

**Версия:** 1.0 |**Заявляемый уровень:** MLOps Level 2

---

## 1. Предыстория

**OnSpeak** — on-demand платформа живых разговорных сессий на английском языке.

**Проблемы:**
1. Churn ~70% после 1-й сессии из-за случайного подбора тьютора
2. Субъективный фидбек тьюторов

Cambly и Preply ушли с рынка РФ в 2022 году — ниша on-demand speaking practice не закрыта.

---

## 2. Ценностное предложение

ML-система персонализирует:
- **(А) Подбор тьютора** (matching → rebook rate↑)
- **(Б) AI-фидбек после сессии** (retention↑)

**Для бизнеса:** rebook rate↑ → ARPU↑ → LTV↑ без роста CAC.

---

## 3. Цели

| ID | Цель | Бизнес-эффект |
|----|------|---------------|
| Г1 | Rebook rate 15% → 32% за 6 мес через ML-matching | ARPU↑ |
| Г2 | AI-фидбек: rate ≥ 75% | Retention D30↑ |
| Г3 | Availability rate ≥ 88% | CAC↓ |
| Г4 | Авто-переобучение без ручного труда | Качество↑ в продакшене |

---

## 4. Решение — MLOps Level 2

**Заявляемый уровень:** 2

### Компоненты

| Компонент | Технология |
|-----------|------------|
| Версионирование | Git + DVC |
| CI/CD | GitHub Actions: автотесты, docker build, деплой в k8s |
| Feature Store | Redis (online) + PostgreSQL (offline) |
| ML-сервисы | FastAPI + Docker: Matching, Feedback, RecSys |
| Оркестратор | Apache Airflow (еженедельный retrain DAG) |
| Эксперименты | MLflow (параметры, метрики, registry) |
| Мониторинг | Grafana + Prometheus + Evidently AI (drift) |
| Traffic switching | Kubernetes canary 5% → 20% → 100% |

### Полный жизненный цикл (Level 2)


**НЕ входит в v1:** собственная LLM, self-hosted Whisper, real-time retrain.

---

## 5. Осуществимость

| Ресурс | Значение |
|--------|----------|
| Команда | 1 ML Engineer + 1 Backend Engineer + 0.5 DevOps + 0.5 PM |
| Облако | Yandex Cloud |
| API | OpenAI GPT-4o + Whisper |
| Данные | Mozilla CommonVoice (публичный), онбординг-анкеты (день 1) |
| Бюджет | 6.3 млн руб. CAPEX |
| Риск холодного старта | Mitigated — rule-based baseline v0 |

---

## 6. Данные

| Тип | Источник | Разметка | Доступность |
|-----|----------|----------|-------------|
| Профили студентов/тьюторов | Онбординг-анкета | Авто (формы) | День 1 |
| Исходы сессий rebook=0/1 | Логи платформы | Авто (событие) | Мес. 1 |
| Транскрипты ASR | Whisper | Ручная разметка 500 сессий | Мес. 2 |
| Аудио для fine-tuning | CommonVoice + сессии | Ручная разметка 500 аудио | День 1 |
| Рейтинг фидбека | In-app кнопка | Авто (клик) | День 1 |
| Клики по темам | Логи кликов | Авто (implicit) | Мес. 1 |

---

## 7. Метрики

| Приоритет | Метрика | Тип | Цель |
|-----------|---------|-----|------|
| 1 | Rebook rate | Бизнес (primary) | ≥ 32% к мес. 6 |
| 2 | Retention D30 | Бизнес | ≥ 38% |
| 3 | ARPU/мес | Бизнес | ≥ 1250 руб. |
| 4 | NPS | Продуктовый | ≥ 50 |
| 5 | Availability rate | Продуктовый | ≥ 88% |

---

## 8. Оценка качества модели

| Задача | Тип | Метрика | Порог |
|--------|-----|---------|-------|
| Matching | Офлайн | NDCG@3, ROC-AUC | NDCG@3 ≥ 0.75, AUC ≥ 0.75 |
| Matching | Онлайн (A/B) | Rebook rate | +10% vs control |
| ASR | Офлайн | WER | ≤ 8% |
| LLM Feedback | Офлайн | Precision/F1 | Precision ≥ 0.80, F1 ≥ 0.72 |
| LLM Feedback | Онлайн (A/B) | Retention D14 | +5 п.п. vs control |
| RecSys | Офлайн | Precision@3 | ≥ 0.35 |

---

## 9. Подбор модели

| Версия | Мес. | Алгоритм | Критерий перехода |
|--------|------|----------|-------------------|
| Matching v0 | 1–2 | Rule-based (рейтинг + доступность) | Baseline |
| Matching v1 | 3 | LightGBM LambdaRank | AUC ≥ 0.65, ≥ 500 сессий |
| Matching v2 | 4–5 | LightGBM + Two-Tower + FAISS | AUC ≥ 0.75, ≥ 2000 сессий |
| LLM Feedback v0 | 1 | GPT-4o zero-shot | F1 ≥ 0.70 |
| LLM Feedback v1 | 3 | GPT-4o few-shot | F1 ≥ 0.72 |
| RecSys v0 | 4 | Content-Based Filtering | Precision@3 ≥ 0.20 |
| RecSys v1 | 5–6 | Гибрид CB+CF (LightFM) | Precision@3 ≥ 0.35 |

---

## 10. Инференс

| Сервис | Режим | SLO |
|--------|-------|-----|
| Matching | Онлайн real-time | P95 ≤ 500 мс, FAISS-индекс обновляется batch ежедневно в 02:00 |
| ASR + LLM Feedback | Async после сессии | Фидбек студенту в течение 60 сек |
| RecSys | Daily batch | Кэш Redis, latency < 20 мс при запросе |

---

## 11. Обратная связь и MDD

**Сигналы:**
- In-app рейтинг (1–5 звёзд)
- Фидбек
- Rebook (implicit)
- Skip rate
- Data drift alert (Evidently AI)

**MDD:** ДА. Все архитектурные решения фиксируются в ADR-документах на основе статистических тестов.

---

## 12. Управление проектом

### Команда

| Роль | FTE | Зона ответственности |
|------|-----|----------------------|
| ML Engineer | 1.0 | Модели, MLflow, Airflow, Evidently |
| Backend Engineer | 1.0 | FastAPI, Feature Store, API |
| DevOps | 0.5 | Kubernetes, CI/CD, Grafana |
| Product Manager | 0.5 | A/B-тесты, метрики |

### Дорожная карта

| Период | Артефакты |
|--------|-----------|
| Мес. 1–2 | MVP: rule-based matching, Whisper API, GPT-4o, базовый мониторинг |
| Мес. 3 | MLflow + DVC + Feature Store + Matching v1 + A/B-тест |
| Мес. 4 | Airflow retrain DAG + Evidently drift monitoring |
| Мес. 5 | RecSys v0 + Matching v2 + CI/CD GitHub Actions |
| Мес. 6 | RecSys v1 + все A/B-тесты + canary release |