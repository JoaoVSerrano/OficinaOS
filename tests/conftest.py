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


# ---------------------------------------------------------------------------
# Gateway com auth-service simulado (usuários escolhidos pelo cabeçalho X-Test-User)
# ---------------------------------------------------------------------------
import itertools  # noqa: E402
from types import SimpleNamespace  # noqa: E402


class FakeAuth:
    """Simula o auth-service para os testes do gateway."""

    def __init__(self):
        self.users: dict[int, dict] = {}
        self._ids = itertools.count(1)
        self.indisponivel = False

    def add(self, role, oficina_id, nome=None, email=None):
        uid = next(self._ids)
        self.users[uid] = {'id': uid, 'role': role, 'oficina_id': oficina_id,
                           'nome': nome or f'{role}{uid}', 'email': email or f'{role}{uid}@oficinaos.example'}
        return uid

    @staticmethod
    def _resp(status, payload):
        return SimpleNamespace(status_code=status, json=lambda: payload, headers={}, raw=SimpleNamespace(headers={}),
                               text='', request=None, url='')

    def __call__(self, method, path, **kwargs):
        from flask import request
        import requests as _rq
        if self.indisponivel:
            raise _rq.ConnectionError('auth fora do ar')
        if path == '/me':
            uid = request.headers.get('X-Test-User')
            user = self.users.get(int(uid)) if uid else None
            return self._resp(200, {'user': user}) if user else self._resp(401, {'error': 'Não autenticado.'})
        if path == '/internal/register':
            body = kwargs['json']
            if any(u['email'] == body['email'] for u in self.users.values()):
                return self._resp(409, {'error': 'Já existe uma conta com esse e-mail.'})
            uid = self.add(body['role'], body['oficina_id'], body['nome'], body['email'])
            return self._resp(201, {'user': self.users[uid]})
        if path.startswith('/internal/oficinas/') and path.endswith('/usuarios'):
            oid = int(path.split('/')[3])
            return self._resp(200, {'usuarios': [u for u in self.users.values() if u['oficina_id'] == oid]})
        if path.startswith('/internal/users/') and path.endswith('/oficina'):
            uid = int(path.split('/')[3])
            self.users[uid]['oficina_id'] = kwargs['json']['oficina_id']
            return self._resp(200, {'user': self.users[uid]})
        raise AssertionError(f'rota do auth não simulada: {method} {path}')


@pytest.fixture
def gw(monkeypatch):
    """Gateway com SQLite em memória, auth simulado e log capturado."""
    from backend import app as core, dominio
    from backend.database import Base
    _, scope = make_sqlite_scope(Base)
    monkeypatch.setattr(dominio, 'session_scope', scope)
    auth = FakeAuth()
    eventos: list[dict] = []
    monkeypatch.setattr(core, '_forward_to_auth', auth)
    monkeypatch.setattr(core, 'log_event',
                        lambda acao, usuario_id=None, detalhe='': eventos.append(
                            {'acao': acao, 'usuario_id': usuario_id, 'detalhe': detalhe}))
    monkeypatch.setattr(core, 'ensure_schema', lambda: None)
    core.app.config['TESTING'] = True
    with core.app.test_client() as c:
        def como(uid):
            return {'headers': {'X-Test-User': str(uid)}}
        yield SimpleNamespace(client=c, auth=auth, eventos=eventos, como=como, scope=scope)
