# OnSpeak — SLI и SLO по трём уровням

Индикаторы качества обслуживания (SLI) и целевые уровни (SLO) для ML-инфраструктуры OnSpeak.

---

## Уровень 1 — Технические SLI/SLO

| Компонент | SLI | SLO | Алерт при |
|-----------|-----|-----|-----------|
| Matching API | P95 latency | ≤ 500 мс | > 700 мс за 5 мин |
| Matching API | Error rate (5xx) | < 0.5% | > 1% за 10 мин |
| Matching API | Availability | ≥ 99.5%/мес | < 99% — инцидент |
| ASR Service | P95 latency транскрипции | ≤ 30 сек | > 60 сек |
| LLM Feedback | P95 latency фидбека | ≤ 60 сек | > 90 сек |
| RecSys API | P95 из кэша | ≤ 20 мс | > 50 мс |
| Feature Store Redis | P99 read latency | ≤ 5 мс | > 20 мс |
| PostgreSQL | CPU utilization | < 70% | > 85% за 15 мин |
| Kubernetes nodes | Memory utilization | < 80% | > 90% |
| CI/CD pipeline | Build + deploy time | ≤ 10 мин | > 20 мин — review |

---

## Уровень 2 — Модельные SLI/SLO

| Модель | SLI | SLO | Действие при нарушении |
|--------|-----|-----|------------------------|
| Matching (LightGBM) | NDCG@3 на hold-out | ≥ 0.70 | Trigger retraining DAG |
| Matching | ROC-AUC (еженедельный eval) | ≥ 0.70 | Alert ML Engineer |
| Matching | Data drift PSI | PSI < 0.20 | Срочное переобучение |
| ASR (Whisper) | WER на выборке 50 сессий/нед | ≤ 10% | Fine-tuning план |
| LLM Feedback | Precision ошибок | ≥ 0.75 | Revision prompt/few-shot |
| LLM Feedback | 👍-rate (7-дневный) | ≥ 65% | Alert + UX review |
| RecSys | Precision@3 (backtesting) | ≥ 0.25 | Retrain plan |

---

## Уровень 3 — Бизнес SLI/SLO

| Метрика | SLI | SLO | Реакция при нарушении |
|---------|-----|-----|-----------------------|
| Rebook rate | Доля повторных записей | ≥ 25% к мес. 3, ≥ 32% к мес. 6 | Анализ matching quality |
| Retention D30 | Доля активных на 30-й день | ≥ 35% | Анализ feedback 👍-rate |
| Session completion rate | Доля завершённых сессий | ≥ 85% | Анализ tech stability |
| Availability rate | Доля запросов с тьютором сразу | ≥ 85% | Supply forecast review |
| NPS | Net Promoter Score | ≥ 45 | CustDev + UX review |
| Churn rate | Не вернулись 30+ дней | ≤ 8%/мес | Retention campaign |

---

## Уровни severity

| Уровень | Описание | Триггер | Время реакции | Действие |
|---------|----------|---------|---------------|----------|
| **P0 (Critical)** | Критический | Availability < 99% или completion < 75% | < 15 мин | Rollback |
| **P1 (High)** | Высокий | ML-метрика ниже SLO или drift PSI > 0.2 | < 4 часа | Retrain / hotfix |
| **P2 (Medium)** | Средний | Бизнес-метрика ниже SLO 3+ дня | < 24 часа | План улучшений |
| **P3 (Low)** | Низкий | Тренд ухудшения, SLO не нарушен | — | Фиксация в backlog |