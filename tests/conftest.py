"""Configuração global de fixtures e ambiente para execução de testes pytest.

Define variáveis de ambiente mínimas fictícias para permitir a importação e
execução de testes unitários sem dependência de serviços externos reais
(banco de dados MariaDB, MinIO, Redis, etc.).
"""
from __future__ import annotations

import os

_DEFAULT_TEST_ENV = {
    'DB_HOST': 'localhost',
    'DB_PORT': '3306',
    'DB_USER': 'test_user',
    'DB_PASSWORD': 'test_password',
    'DB_NAME': 'test_db',
    'FLASK_SECRET_KEY': 'test-flask-secret-key-1234567890',
    'AUTH_SECRET_KEY': 'test-auth-secret-key-1234567890',
    'INTERNAL_TOKEN': 'test-internal-token-1234567890',
    'MINIO_ACCESS_KEY': 'test-minio-key',
    'MINIO_SECRET_KEY': 'test-minio-secret',
    'REDIS_URL': 'redis://localhost:6379/0',
    'STRIPE_SECRET_KEY': 'sk_test_fake_key_12345',
    'STRIPE_WEBHOOK_SECRET': 'whsec_fake_secret_12345',
    'STRIPE_PRICE_ID': 'price_fake_12345',
    'STRIPE_PUBLISHABLE_KEY': 'pk_test_fake_12345',
    'GOOGLE_CLIENT_ID': 'fake-client-id.apps.googleusercontent.com',
    'GOOGLE_CLIENT_SECRET': 'fake-client-secret',
}

for _key, _value in _DEFAULT_TEST_ENV.items():
    os.environ.setdefault(_key, _value)

import pytest


@pytest.fixture
def client():
    from backend.app import app
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# Banco SQLite em memória para testes de rotas (sem MariaDB)
# ---------------------------------------------------------------------------
from contextlib import contextmanager  # noqa: E402

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402


def make_sqlite_scope(base):
    """Cria tabelas de `base` num SQLite em memória e devolve (engine, session_scope)."""
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    @contextmanager
    def scope():
        s = maker()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    return engine, scope


@pytest.fixture
def auth_client(monkeypatch):
    from auth_service import app as auth_app
    from auth_service.database import Base
    _, scope = make_sqlite_scope(Base)
    monkeypatch.setattr(auth_app, 'session_scope', scope)
    monkeypatch.setattr(auth_app, '_schema_ready', True)
    auth_app.app.config['TESTING'] = True
    with auth_app.app.test_client() as c:
        yield c
