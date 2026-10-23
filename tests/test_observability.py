from __future__ import annotations

from contextlib import contextmanager, nullcontext
from unittest.mock import Mock

from auth_service import app as auth_module
from log_service import app as log_module


def healthy_database_context():
    return nullcontext(Mock(execute=Mock()))


def test_auth_health_requires_database_and_minio(monkeypatch):
    monkeypatch.setattr(auth_module, 'session_scope', healthy_database_context)
    monkeypatch.setattr(auth_module, 'get_minio_client', lambda: Mock(list_buckets=Mock()))

    with auth_module.app.test_client() as client:
        response = client.get('/health')

    assert response.status_code == 200
    body = response.get_json()
    assert body['status'] == 'healthy'
    assert body['service'] == 'auth-service'
    assert body['dependencies']['database']['status'] == 'connected'
    assert body['dependencies']['minio']['status'] == 'connected'
    assert {'version', 'uptime_seconds', 'latency_ms', 'timestamp'} <= body.keys()


def test_auth_health_returns_503_when_database_is_down(monkeypatch):
    @contextmanager
    def broken_database():
        raise RuntimeError('database unavailable')
        yield

    monkeypatch.setattr(auth_module, 'session_scope', broken_database)
    monkeypatch.setattr(auth_module, 'get_minio_client', lambda: Mock(list_buckets=Mock()))

    with auth_module.app.test_client() as client:
        response = client.get('/health')

    assert response.status_code == 503
    body = response.get_json()
    assert body['status'] == 'unhealthy'
    assert body['dependencies']['database']['status'] == 'disconnected'


def test_log_health_requires_redis(monkeypatch):
    monkeypatch.setattr(log_module, 'get_redis', lambda: Mock(ping=Mock()))

    with log_module.app.test_client() as client:
        response = client.get('/health')

    assert response.status_code == 200
    body = response.get_json()
    assert body['status'] == 'healthy'
    assert body['service'] == 'log-service'
    assert body['dependencies']['redis']['status'] == 'connected'
    assert {'version', 'uptime_seconds', 'latency_ms', 'timestamp'} <= body.keys()


def test_log_health_returns_503_when_redis_is_down(monkeypatch):
    def unavailable_redis():
        raise RuntimeError('redis unavailable')

    monkeypatch.setattr(log_module, 'get_redis', unavailable_redis)

    with log_module.app.test_client() as client:
        response = client.get('/health')

    assert response.status_code == 503
    body = response.get_json()
    assert body['status'] == 'unhealthy'
    assert body['dependencies']['redis']['status'] == 'disconnected'
