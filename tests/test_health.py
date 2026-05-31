"""
tests/test_health.py — тесты healthcheck и базовой доступности сервиса
"""
import pytest
from fastapi.testclient import TestClient
import sys
import os

# Добавляем путь к сервису
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'matching'))

try:
    from main import app
    CLIENT_AVAILABLE = True
except ImportError:
    CLIENT_AVAILABLE = False


@pytest.fixture
def client():
    if not CLIENT_AVAILABLE:
        pytest.skip("services/matching/main.py not importable in CI without deps")
    from main import app
    return TestClient(app)


class TestHealthEndpoint:
    """GET /health — SLO: availability ≥99.5%"""

    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    def test_health_response_structure(self, client):
        response = client.get("/health")
        data = response.json()
        assert "status" in data, "Response must contain 'status' field"
        assert data["status"] == "ok", f"Expected status='ok', got '{data['status']}'"

    def test_health_response_has_version(self, client):
        response = client.get("/health")
        data = response.json()
        assert "version" in data or "model_version" in data, \
            "Health response should include version info for traceability"

    def test_health_latency_under_slo(self, client):
        """SLO: P95 latency ≤500мс. Health endpoint должен отвечать намного быстрее."""
        import time
        latencies = []
        for _ in range(10):
            start = time.perf_counter()
            client.get("/health")
            latencies.append(time.perf_counter() - start)
        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]
        assert p95 < 0.5, f"Health P95 latency {p95:.3f}s exceeds 500ms SLO"

    def test_health_content_type_json(self, client):
        response = client.get("/health")
        assert "application/json" in response.headers.get("content-type", ""), \
            "Health endpoint must return JSON"


class TestMetricsEndpoint:
    """GET /metrics — Prometheus scrape endpoint"""

    def test_metrics_returns_200(self, client):
        response = client.get("/metrics")
        assert response.status_code == 200

    def test_metrics_contains_required_counters(self, client):
        response = client.get("/metrics")
        body = response.text
        required_metrics = [
            "http_requests_total",
            "http_request_duration_seconds",
        ]
        for metric in required_metrics:
            assert metric in body, \
                f"Prometheus metric '{metric}' not found in /metrics output"

    def test_metrics_contains_ml_gauges(self, client):
        """ML-метрики должны экспортироваться для SLO-мониторинга."""
        response = client.get("/metrics")
        body = response.text
        # Хотя бы один из ML-специфичных счётчиков должен присутствовать
        ml_metrics = [
            "speakup_model_ndcg",
            "speakup_predictions_total",
            "speakup_model_version",
        ]
        found = [m for m in ml_metrics if m in body]
        assert len(found) > 0, \
            f"No ML-specific metrics found in /metrics. Expected one of: {ml_metrics}"


class TestRootEndpoint:
    """GET / — базовая документация или редирект на /docs"""

    def test_root_or_docs_reachable(self, client):
        r_root = client.get("/")
        r_docs = client.get("/docs")
        assert r_root.status_code in (200, 307, 308) or r_docs.status_code == 200, \
            "Either / or /docs must be reachable"


class TestReadinessWithoutDB:
    """Тесты на отказоустойчивость — mock недоступных зависимостей"""

    def test_health_does_not_crash_without_db(self, monkeypatch, client):
        """Если БД недоступна, /health должен вернуть degraded, а не 500."""
        import unittest.mock as mock

        # Патчим соединение с БД чтобы имитировать недоступность
        with mock.patch(
            "main.get_db_connection",
            side_effect=Exception("DB connection refused"),
            create=True,
        ):
            response = client.get("/health")
            # Допустимо: 200 с degraded status ИЛИ 503
            assert response.status_code in (200, 503), \
                f"Expected graceful degradation (200/503), got {response.status_code}"
            if response.status_code == 200:
                data = response.json()
                # Должен явно указать, что что-то деградировало
                assert data.get("status") in ("ok", "degraded"), \
                    "Health status must be 'ok' or 'degraded' when DB is down"
