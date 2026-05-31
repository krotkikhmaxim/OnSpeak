# OnSpeak ML — Matching Service (LightGBM)

**Единственная production ML-задача**: подбор тьютора для разговорной сессии английского языка.

Остальные задачи (ASR, LLM Feedback, RecSys) реализованы как `stub` и возвращают фиктивные ответы.  
Репозиторий демонстрирует **MLOps Level 2** с полным жизненным циклом модели: от трекинга экспериментов до мониторинга SLO и автоматического переобучения.

---

## Содержание

- [Бизнес-контекст](#бизнес-контекст)
- [Структура репозитория](#структура-репозитория)
- [Компоненты](#компоненты)
- [ML-манифест (кратко)](#ml-манифест-кратко)
- [IaC: docker-compose](#iac-docker-compose)
- [SLI/SLO: три уровня](#slislo-три-уровня)
- [MDD + ADR](#mdd--adr)

---

## Бизнес-контекст

**SpeakUP** — on-demand платформа разговорных сессий на английском.  
Проблема: ~70% пользователей уходят после первой сессии из-за случайного подбора тьютора.  
Цель: повысить **rebook rate** с 15% до ≥32% за счёт персонального ML-мэтчинга.

### Используемые данные (три таблицы)

| Таблица   | Назначение                         |
|-----------|------------------------------------|
| `students` | Профиль студента (id, уровень CEFR, тема, предпочтение по акценту) |
| `tutors`   | Профиль тьютора (id, специализация, рейтинг, доступность) |
| `sessions` | Исходы сессий (student_id, tutor_id, rebook=0/1, created_at) |

На старте используется 500 синтетических сессий (`init.sql`), затем система пополняется реальными данными.

**Три таблицы данных :**
- `students` — профиль студента (id, cefr_level, topic, accent_preference)
- `tutors` — профиль тьютора (id, specialization, rating, availability)
- `sessions` — исходы сессий (student_id, tutor_id, rebook=0/1, created_at)

***
## Структура репозитория
```
speakup-ml/
├── docker-compose.yml          ← IaC: 5 сервисов с healthcheck
├── .github/
│   └── workflows/
│       ├── ci.yml              ← lint + tests (всегда)
│       ├── cd.yml              ← build + deploy (на main)
│       └── destroy.yml         ← деинсталляция (workflow_dispatch)
├── services/
│   └── matching/
│       ├── Dockerfile          ← HEALTHCHECK встроен
│       ├── main.py             ← FastAPI: /match + /health + /metrics
│       ├── model.py            ← LightGBM train/predict
│       ├── features.py         ← feature engineering
│       └── requirements.txt
├── dags/
│   └── retrain_dag.py          ← Airflow DAG (weekly retrain)
├── notebooks/
│   └── mdd_analysis.ipynb      ← MDD: Welch t-test + визуализация
├── docs/
│   ├── manifest.md             ← ML-манифест (Шаг 2)
│   ├── sli_slo.md              ← SLI/SLO таблицы (Шаг 4)
│   └── adr_001.md              ← ADR документ (Шаг 5)
├── infra/
│   └── terraform/              ← опционально: Yandex Cloud IaC
│       ├── main.tf
│       └── variables.tf
├── monitoring/
│   └── prometheus.yml
├── tests/
│   ├── test_matching.py
│   └── test_health.py
└── README.md                   ← инструкция: docker-compose up + docker ps
```

***
## Компоненты: 
| Компонент | Технология | Зачем нужен | Критерий |
|---|---|---|---|
| Git-репозиторий | GitHub | Версионирование кода | Level 2: версионирование |
| Feature Store (offline) | PostgreSQL | Хранение сессий, профилей | Level 2: фича-стор |
| Feature Store (online) | Redis | Кэш предсказаний (TTL 1ч) | Level 2: фича-стор |
| ML Service | FastAPI + LightGBM | Сервинг через API | Level 2: API сервинг |
| Experiment tracking | MLflow | Трекинг метрик, registry | Level 2: управление экспериментами |
| Оркестратор | Airflow | Retrain DAG | Level 2: оркестратор |
| Мониторинг | Prometheus + Grafana | SLO tracking | Level 2: мониторинг |
| CI/CD | GitHub Actions | Авто-деплой + деинсталляция | Критерий 3: IaC |
| Контейнеризация | Docker + docker-compose | `docker ps` → STATUS Up(healthy) | Критерий 3: healthcheck |

**Что намеренно убрано:** Evidently AI (drift — заменяется простой метрикой в Airflow DAG), FAISS (replaced by простой `ORDER BY score LIMIT 3` в PostgreSQL на старте), Kafka (не нужна при одной ML-задаче), отдельный feedback/recsys service.

***
## ML-манифест 
### 1. Предыстория
SpeakUP — on-demand платформа разговорных сессий на английском. Проблема: churn ~70% после первой сессии из-за случайного подбора тьютора. Cambly ушёл с рынка РФ в 2022 г. — ниша не закрыта.
### 2. Ценностное предложение
ML-matching подбирает тьютора по уровню, теме и доступности за ≤500 мс. Результат: rebook rate ↑ → ARPU ↑ → LTV ↑ без роста CAC.
### 3. Цели
- Г1: rebook rate 15% → 32% через ML-matching к мес. 6
- Г2: Latency P95 ≤ 500 мс при 100 concurrent запросах
- Г3: Автоматическое переобучение при накоплении ≥500 новых сессий
### 4. Решение — **Уровень 2**
**Уровень зрелости: 2** (MLOps Level 2 по Google Cloud Architecture).

Что есть:
- ✅ Версионирование кода (Git + DVC для данных)
- ✅ CI/CD (GitHub Actions: test → build → deploy → destroy)
- ✅ Feature Store (PostgreSQL offline + Redis online)
- ✅ API сервинг (FastAPI /match + /health)
- ✅ Мониторинг (Prometheus + Grafana, метрика NDCG@3)
- ✅ Управление экспериментами (MLflow)
- ✅ Оркестратор (Airflow, weekly retrain DAG)

Что НЕ входит в v1: ASR, LLM feedback, RecSys (заглушки), self-hosted Whisper, real-time retrain.

**Полный жизненный цикл пайплайна:**
```
Новые данные → Airflow DAG (понедельник 02:00)
  → check_data (≥500 сессий?)
  → feature_engineering
  → train LightGBM
  → evaluate (NDCG@3 ≥ 0.70?)
  → [ДА] MLflow staging → canary 5% → guardrail OK?
  → [ДА] 100% трафик → старая модель decommissioned
  → [НЕТ] rollback, alert, production не меняется
```

### 5. Осуществимость
**Облако**: Yandex Cloud. MLflow: self-hosted в docker-compose. Данные: синтетические (seed-данные в `init.sql` — 500 сессий для старта).

### 6. Данные
- **Обучение:** seed-данные (500 синтетических сессий в `init.sql`) + накопленные реальные сессии
- **Прод:** логи платформы → таблица `sessions` в PostgreSQL в реальном времени
- **Разметка:** авто (rebook=1 если студент записался повторно к тому же тьютору в течение 7 дней)
### 7. Метрики (приоритет)
1. **Rebook rate** (бизнес, primary) — цель ≥32% к мес. 6
2. **P95 latency** (технический) — ≤500 мс
3. **NDCG@3** (ML) — ≥0.70
### 8. Оценка качества модели
- **Офлайн:** NDCG@3, ROC-AUC на hold-out 20%, backtesting
- **Онлайн:** rebook rate (A/B-тест 50/50, 1000 пользователей, 3 недели, p-value < 0.05)
### 9. Подбор модели (итеративный)
| Итерация | Алгоритм | Критерий перехода |
|---|---|---|
| v0 | Rule-based: топ-3 по рейтингу + доступность | Baseline, работает сразу |
| v1 | LightGBM LambdaRank (табличные фичи) | AUC ≥ 0.65, ≥ 500 сессий |
| v2 | LightGBM + дополнительные фичи (rolling rebook rate 30 дн.) | AUC ≥ 0.75, ≥ 2000 сессий |
### 10. Инференс
**Онлайн (real-time):** при каждом запросе `/match` → фичи из Redis → скоринг LightGBM → топ-3 тьютора. P95 ≤ 500 мс.
### 11. Обратная связь и MDD
**Сигналы:** rebook (implicit, авто), in-app рейтинг 1–5 звёзд (explicit).
**MDD: ДА.** Все архитектурные решения фиксируются в ADR по результатам статистических тестов.
### 12. Управление проектом
| Роль | FTE | Артефакт |
|---|---|---|
| ML Engineer (студент) | 1.0 | Все компоненты |

| Неделя | Задача | Артефакт |
|---|---|---|
| 1 | docker-compose + PostgreSQL + Redis + seed данные | `docker ps` STATUS Up(healthy) |
| 2 | FastAPI `/match` (rule-based v0) + `/health` + GitHub Actions CI | Работающий эндпоинт |
| 3 | MLflow + LightGBM v1 + Airflow DAG | Retrain pipeline |
| 4 | Prometheus + Grafana + docs/ (manifest, sli_slo, ADR) | Полный пакет |
| 5 | Деплой в облако + README с `docker ps` скриншотом | Ссылка на прод |
| 6 | MDD analysis (notebook) + финальный ADR | 10/10 |

***
## IaC: docker-compose
```yaml
# docker-compose.yml — 5 сервисов, все с healthcheck
version: "3.9"
services:
  postgres:      # Feature Store offline
  redis:         # Feature Store online
  mlflow:        # Experiment tracking
  airflow:       # Orchestrator
  matching-api:  # ML Service (FastAPI)
  prometheus:    # Monitoring
  grafana:       # Dashboards
```

**Деинсталляция** (обязательно для 2 баллов):
```bash
# В .github/workflows/destroy.yml
docker-compose down -v --remove-orphans
# или Terraform destroy для облака
```

**Команды для скриншота `docker ps`:**
```bash
docker-compose up -d
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
# Ожидаемый вывод: STATUS = Up (healthy) для всех сервисов
```

***
## SLI/SLO: три уровня
### Технический уровень
| SLI | SLO | Алерт |
|---|---|---|
| P95 latency `/match` | ≤ 500 мс | > 700 мс за 5 мин |
| Error rate 5xx | < 0.5% | > 1% за 10 мин |
| Uptime | ≥ 99.5%/мес | < 99% |
| CPU | < 70% | > 85% за 15 мин |
| Memory | < 80% | > 90% |
### Модельный уровень
| SLI | SLO | Алерт |
|---|---|---|
| NDCG@3 (еженедельный eval) | ≥ 0.70 | < 0.65 → retrain |
| ROC-AUC | ≥ 0.70 | < 0.65 → alert |
| Data drift (PSI) | PSI < 0.20 | > 0.20 → срочный retrain |
### Бизнес-уровень
| SLI | SLO | Алерт |
|---|---|---|
| Rebook rate (7-дн. скользящее) | ≥ 25% к мес.3, ≥ 32% к мес.6 | Снижение 3+ дней подряд |
| Session completion rate | ≥ 85% | < 80% |
| Churn rate | ≤ 8%/мес | > 10% |

***
## MDD + ADR
### Гипотезы
- **H0:** Среднее P95 latency улучшенной системы ≥ существующей (улучшений нет)
- **H1:** Среднее P95 latency улучшенной системы < существующей (улучшение достоверно)
### Тест: Welch t-test (двусторонний, alpha=0.05)
По данным из условия (n=500 000):
- Существующая система: mean=3.50 сек, P95=4.15 сек
- Улучшенная система: mean=2.00 сек, P95=2.65 сек
- t-статистика = 265.9, p-value ≈ 0 (< 0.05)
- **Вывод: H0 отвергается** → мигрировать на улучшенную архитектуру
### ADR-001 
```markdown
# ADR-001: Миграция Matching Service на FAISS ANN + Redis cache

## Status: Accepted

## Context
P95 latency = 4.15 сек, SLO = ≤ 2.5 сек. SLO нарушен.
Причина: O(n) перебор в PostgreSQL при n > 1000 тьюторов.

## Decision
H0: latency_improved ≥ latency_existing
H1: latency_improved < latency_existing
Тест: Welch t-test, alpha=0.05
t=265.9, p≈0 → H0 отвергается
→ Мигрировать на FAISS ANN-индекс (daily rebuild) + Redis cache топ-50

## Consequences
(+) P95: 4.15с → 2.65с (-36%), SLO восстановлен
(-) FAISS rebuild ежедневно → Airflow task failure alert
```
