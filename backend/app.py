from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import requests
from flask import Flask, Response, jsonify, request, send_from_directory
from prometheus_flask_exporter import PrometheusMetrics
from sqlalchemy import delete, select

from backend.database import session_scope, upgrade_database
from backend.models import Comment, Favorite


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / 'static'
TMDB_BASE_URL = 'https://api.themoviedb.org/3'
TMDB_IMAGE_BASE_URL = 'https://image.tmdb.org/t/p/w500'
_LAST_KNOWN_CATALOG: list[dict[str, Any]] = []

app = Flask(__name__)
_flask_secret = os.getenv('FLASK_SECRET_KEY')
if not _flask_secret:
    import sys
    print(
        '[backend] ERRO: variável FLASK_SECRET_KEY não definida. '
        'Defina-a na seção *Environment* da stack no Portainer.',
        file=sys.stderr,
    )
    sys.exit(1)
app.secret_key = _flask_secret
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE=os.getenv('SESSION_COOKIE_SAMESITE', 'Lax'),
    SESSION_COOKIE_SECURE=os.getenv('SESSION_COOKIE_SECURE', '0') == '1',
)
metrics = PrometheusMetrics(app)

import time as _time
import json as _json
import redis as _redis

START_TIME = _time.time()
_redis_pool: _redis.ConnectionPool | None = None
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379/0')


def get_redis() -> _redis.Redis:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = _redis.ConnectionPool.from_url(
            REDIS_URL,
            decode_responses=True,
            max_connections=20,
        )
    return _redis.Redis(connection_pool=_redis_pool)


def get_client_ip() -> str:
    """Extrai o IP real do cliente considerando cabeçalhos de proxies confiáveis."""
    for header in ('X-Real-IP', 'CF-Connecting-IP', 'X-Forwarded-For'):
        val = request.headers.get(header)
        if val:
            parts = [p.strip() for p in val.split(',') if p.strip()]
            for part in parts:
                # Ignora faixas internas óbvias se houver outro endereço
                if not (part.startswith(('10.', '127.')) or (part.startswith('172.') and 16 <= int(part.split('.')[1]) <= 31)):
                    return part
            if parts:
                return parts[0]
    return request.remote_addr or '127.0.0.1'


# Rate limiting simples em memória / Redis
_local_rate_limit: dict[str, list[float]] = {}

def check_rate_limit(key: str, max_requests: int = 30, window_seconds: int = 60) -> bool:
    """Retorna True se a requisição é permitida, False se excedeu o limite."""
    now = _time.time()
    try:
        r = get_redis()
        r_key = f'ratelimit:{key}'
        current = r.incr(r_key)
        if current == 1:
            r.expire(r_key, window_seconds)
        return current <= max_requests
    except Exception:
        # Fallback para controle em memória
        timestamps = _local_rate_limit.setdefault(key, [])
        # Remove timestamps fora da janela
        _local_rate_limit[key] = [t for t in timestamps if now - t < window_seconds]
        if len(_local_rate_limit[key]) >= max_requests:
            return False
        _local_rate_limit[key].append(now)
        return True


# ---------------------------------------------------------------------------
# Auth-service proxy helpers
# ---------------------------------------------------------------------------


def auth_service_url() -> str:
    return os.getenv('AUTH_SERVICE_URL', 'http://auth-service:3000')


def log_service_url() -> str:
    return os.getenv('LOG_SERVICE_URL', 'http://log-service:4000')


def payment_service_url() -> str:
    return os.getenv('PAYMENT_SERVICE_URL', 'http://payment-service:5000')


def minio_is_ready() -> bool:
    """Confere conectividade com o object storage usado pelos avatares."""
    try:
        from minio import Minio

        raw_endpoint = os.getenv('MINIO_ENDPOINT', 'minio:9000')
        endpoint = raw_endpoint.split('://')[-1] if '://' in raw_endpoint else raw_endpoint
        access_key = os.getenv('MINIO_ACCESS_KEY', '')
        secret_key = os.getenv('MINIO_SECRET_KEY', '')
        if not access_key or not secret_key:
            app.logger.warning('MINIO_ACCESS_KEY ou MINIO_SECRET_KEY não definidos — MinIO desabilitado.')
            return False
        client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=False,
        )
        client.list_buckets()
        return True
    except Exception as exc:
        app.logger.warning('MinIO indisponível em healthcheck: %s', exc)
        return False


def internal_token() -> str:
    return os.getenv('INTERNAL_TOKEN', '')


def _forward_to_auth(method: str, path: str, **kwargs) -> requests.Response:
    """Encaminha uma requisição ao microsserviço de autenticação."""
    url = f'{auth_service_url()}{path}'
    # Repassa o cookie de sessão para que o auth-service reconheça o usuário
    cookies = request.cookies
    headers = kwargs.pop('headers', {})
    headers['X-Internal-Token'] = internal_token()
    client_ip = get_client_ip()
    headers['X-Forwarded-For'] = client_ip
    headers['X-Real-IP'] = client_ip
    return requests.request(method, url, cookies=cookies, headers=headers, timeout=30, **kwargs)


def _auth_response_payload(resp: requests.Response) -> dict[str, Any]:
    try:
        payload = resp.json()
    except ValueError:
        app.logger.error(
            'Auth-service retornou resposta não JSON em %s %s: status=%s body=%r',
            resp.request.method if resp.request else 'UNKNOWN',
            resp.url,
            resp.status_code,
            resp.text[:500],
        )
        payload = {'error': 'Serviço de autenticação retornou uma resposta inválida.'}

    if isinstance(payload, dict):
        return payload
    return {'data': payload}


def _set_cookie_headers(resp: requests.Response) -> list[str]:
    headers = resp.raw.headers
    if hasattr(headers, 'getlist'):
        return headers.getlist('Set-Cookie')
    if hasattr(headers, 'get_all'):
        return headers.get_all('Set-Cookie')
    header = resp.headers.get('Set-Cookie')
    return [header] if header else []


def _proxy_auth(method: str, path: str, **kwargs):
    """Faz proxy de uma requisição de auth e retorna a resposta Flask completa."""
    try:
        resp = _forward_to_auth(method, path, **kwargs)
    except requests.RequestException as exc:
        app.logger.error('Auth-service indisponível: %s', exc)
        return jsonify({'error': 'Serviço de autenticação indisponível.'}), 503

    response = jsonify(_auth_response_payload(resp))
    response.status_code = resp.status_code

    # Mantém todos os atributos do cookie assinado pelo auth-service.
    for header in _set_cookie_headers(resp):
        response.headers.add('Set-Cookie', header)

    return response


# ---------------------------------------------------------------------------
# Log de auditoria — envia evento ao log-service (fire-and-forget)
# ---------------------------------------------------------------------------

def log_event(
    acao: str,
    usuario_id: int | None = None,
    detalhe: str | dict = '',
) -> None:
    """Envia um evento de auditoria ao log-service de forma assíncrona.

    Erros de conectividade são registrados no log do app mas nunca
    propagam para o usuário — auditoria nunca deve travar a ação.
    """
    try:
        ip = get_client_ip()

        if isinstance(detalhe, dict):
            detalhe_str = _json.dumps(detalhe, ensure_ascii=False)
        else:
            detalhe_str = str(detalhe)

        requests.post(
            f'{log_service_url()}/log',
            json={
                'usuario_id': usuario_id,
                'acao': acao,
                'detalhe': detalhe_str,
                'ip': ip,
            },
            headers={'X-Internal-Token': internal_token()},
            timeout=3,
        )
    except Exception as exc:
        app.logger.warning('log-service indisponível (evento=%s): %s', acao, exc)


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

def _cors_origins() -> set[str]:
    raw = os.getenv('CORS_ORIGINS', 'http://localhost:4200').strip()
    return {item.strip() for item in raw.split(',') if item.strip()}


@app.after_request
def add_cors_headers(response):
    origin = request.headers.get('Origin')
    if origin and origin in _cors_origins():
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        response.headers['Access-Control-Allow-Methods'] = 'GET,POST,DELETE,OPTIONS'
        response.headers['Vary'] = 'Origin'
    if response.content_type.startswith('text/html'):
        response.headers['Cache-Control'] = 'no-store, max-age=0'
    return response


@app.route('/api/<path:_path>', methods=['OPTIONS'])
def api_preflight(_path: str):
    return ('', 204)


def json_error(message: str, status: int = 400):
    return jsonify({'error': message}), status


# ---------------------------------------------------------------------------
# TMDB helpers
# ---------------------------------------------------------------------------

def normalize_poster_path(poster_path: str | None) -> str | None:
    if not poster_path:
        return None
    return poster_path if poster_path.startswith('http') else f'{TMDB_IMAGE_BASE_URL}{poster_path}'


def tmdb_request(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    api_key = os.getenv('TMDB_API_KEY')
    if not api_key:
        raise RuntimeError('TMDB_API_KEY não configurada no servidor.')

    query = {'api_key': api_key, 'language': os.getenv('TMDB_LANGUAGE', 'pt-BR')}
    if params:
        query.update(params)

    response = requests.get(f'{TMDB_BASE_URL}{path}', params=query, timeout=20)
    response.raise_for_status()
    return response.json()


@lru_cache(maxsize=1)
def get_tom_hanks_person_id() -> int:
    payload = tmdb_request('/search/person', {'query': 'Tom Hanks'})
    results = payload.get('results', [])
    if not results:
        raise RuntimeError('Tom Hanks não foi encontrado na TMDB.')

    for person in results:
        if person.get('name', '').strip().lower() == 'tom hanks':
            return int(person['id'])
    return int(results[0]['id'])


@lru_cache(maxsize=128)
def get_movie_details(movie_id: int) -> dict[str, Any]:
    payload = tmdb_request(f'/movie/{movie_id}')
    return {
        'tmdb_movie_id': int(payload['id']),
        'title': payload.get('title') or payload.get('original_title') or 'Título indisponível',
        'overview': payload.get('overview') or 'Sinopse indisponível.',
        'poster_path': payload.get('poster_path'),
        'poster_url': normalize_poster_path(payload.get('poster_path')),
        'release_date': payload.get('release_date'),
    }


def _catalog_copy(catalog: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [movie.copy() for movie in catalog]


@lru_cache(maxsize=1)
def get_tom_hanks_catalog() -> list[dict[str, Any]]:
    person_id = get_tom_hanks_person_id()
    payload = tmdb_request(f'/person/{person_id}/movie_credits')
    credits = payload.get('cast', [])

    selected = [
        movie
        for movie in sorted(
            credits,
            key=lambda item: (
                item.get('release_date') or '0000-00-00',
                item.get('popularity') or 0,
            ),
            reverse=True,
        )
        if movie.get('id') and movie.get('media_type', 'movie') == 'movie'
    ][:24]

    catalog: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    for movie in selected:
        movie_id = int(movie['id'])
        if movie_id in seen_ids:
            continue
        seen_ids.add(movie_id)
        try:
            details = get_movie_details(movie_id)
        except Exception:
            details = {
                'tmdb_movie_id': movie_id,
                'title': movie.get('title') or movie.get('original_title') or 'Título indisponível',
                'overview': movie.get('overview') or 'Sinopse indisponível.',
                'poster_path': movie.get('poster_path'),
                'poster_url': normalize_poster_path(movie.get('poster_path')),
                'release_date': movie.get('release_date'),
            }
        catalog.append(details)

    global _LAST_KNOWN_CATALOG
    _LAST_KNOWN_CATALOG = _catalog_copy(catalog)
    return catalog


# ---------------------------------------------------------------------------
# Sessão local (o user_id fica na cookie do catálogo após login no auth-service)
# ---------------------------------------------------------------------------

def require_login():
    """Verifica se o usuário está autenticado consultando o auth-service."""
    try:
        resp = _forward_to_auth('GET', '/me')
        if resp.status_code != 200:
            return None, json_error('Faça login para continuar.', 401)
        data = resp.json()
        user_id = int(data['user']['id'])
        return user_id, None
    except requests.RequestException as exc:
        app.logger.error('Auth-service indisponível em require_login: %s', exc)
        return None, json_error('Serviço de autenticação indisponível.', 503)


def require_role(expected_role: str):
    """Verifica autenticação e role do usuário consultando o auth-service.

    Retorna (user_data, None) em caso de sucesso, ou (None, resposta_erro)
    se não autenticado (401) ou sem o papel exigido (403).
    O enforcement real da permissão acontece aqui, no servidor — nunca no cliente.
    """
    try:
        resp = _forward_to_auth('GET', '/me')
        if resp.status_code != 200:
            return None, json_error('Faça login para continuar.', 401)
        data = resp.json()
        user = data.get('user', {})
        role = user.get('role', 'usuario')
        if role != expected_role:
            return None, json_error(
                'Acesso negado. Apenas administradores podem executar esta ação.', 403
            )
        return user, None
    except requests.RequestException as exc:
        app.logger.error('Auth-service indisponível em require_role: %s', exc)
        return None, json_error('Serviço de autenticação indisponível.', 503)


def serialize_movie(movie: dict[str, Any], favorite_ids: set[int], comments: list[dict[str, Any]]):
    movie_id = int(movie['tmdb_movie_id'])
    movie_comments = [item for item in comments if item['tmdb_movie_id'] == movie_id]
    return {
        'tmdb_movie_id': movie_id,
        'title': movie['title'],
        'overview': movie['overview'],
        'poster_path': movie.get('poster_path'),
        'poster_url': movie.get('poster_url'),
        'release_date': movie.get('release_date'),
        'is_favorite': movie_id in favorite_ids,
        'comments': movie_comments,
        'comment_count': len(movie_comments),
        'favorite': movie_id in favorite_ids,
    }


def ensure_schema() -> None:
    upgrade_database()


@app.before_request
def initialize_app():
    if request.method == 'OPTIONS':
        return None
    if not request.path.startswith('/api/'):
        return None
    if not getattr(app, '_schema_attempted', False):
        app._schema_attempted = True
        try:
            ensure_schema()
        except Exception:
            app.logger.exception('Não foi possível garantir o schema do banco na inicialização.')
    return None


# ---------------------------------------------------------------------------
# Health & Readiness
# ---------------------------------------------------------------------------

@app.get('/health')
@app.get('/api/health')
def health():
    db_ok = False
    auth_ok = False
    log_ok = False
    payment_ok = False
    minio_ok = minio_is_ready()

    try:
        with session_scope() as db:
            db.execute(select(1))
        db_ok = True
    except Exception:
        db_ok = False

    try:
        resp = requests.get(f"{auth_service_url()}/health", timeout=2)
        auth_ok = resp.status_code == 200
    except Exception:
        auth_ok = False

    try:
        resp = requests.get(f"{log_service_url()}/health", timeout=2)
        log_ok = resp.status_code == 200
    except Exception:
        log_ok = False

    try:
        resp = requests.get(f"{payment_service_url()}/health", timeout=2)
        payment_ok = resp.status_code == 200
    except Exception:
        payment_ok = False

    status_code = 200 if (db_ok and auth_ok and log_ok and minio_ok) else 503
    return jsonify({
        'status': 'healthy' if status_code == 200 else 'unhealthy',
        'service': 'app-gateway',
        'dependencies': {
            'database': 'connected' if db_ok else 'disconnected',
            'auth_service': 'reachable' if auth_ok else 'unreachable',
            'log_service': 'reachable' if log_ok else 'unreachable',
            'payment_service': 'reachable' if payment_ok else 'unreachable',
            'minio': 'connected' if minio_ok else 'disconnected',
        }
    }), status_code


# ---------------------------------------------------------------------------
# Auth — proxy para o microsserviço de autenticação
# ---------------------------------------------------------------------------

@app.get('/api/auth/me')
def me():
    response = _proxy_auth('GET', '/me')
    if response.status_code == 401:
        return jsonify({'user': None})
    return response


@app.post('/api/auth/register')
def register():
    return _proxy_auth('POST', '/register', json=request.get_json(silent=True) or {})


@app.post('/api/auth/login')
def login():
    payload = request.get_json(silent=True) or {}
    response = _proxy_auth('POST', '/login', json=payload)
    # Loga o evento apenas quando o login for bem-sucedido
    if response.status_code == 200:
        try:
            user_data = response.get_json()
            uid = user_data.get('user', {}).get('id') if user_data else None
            email = payload.get('email', '')
            log_event('login', usuario_id=uid, detalhe={'email': email, 'metodo': 'senha'})
        except Exception:
            log_event('login', detalhe={'email': payload.get('email', ''), 'metodo': 'senha'})
    elif response.status_code == 401:
        log_event('login_falhou', detalhe={'email': payload.get('email', ''), 'motivo': 'credenciais_invalidas'})
    return response


@app.post('/api/auth/logout')
def logout():
    # Obtém o usuário atual antes de deslogar para registrar o ID
    uid = None
    try:
        me_resp = _forward_to_auth('GET', '/me')
        if me_resp.status_code == 200:
            uid = me_resp.json().get('user', {}).get('id')
    except Exception:
        pass
    response = _proxy_auth('POST', '/logout')
    log_event('logout', usuario_id=uid)
    return response


@app.post('/api/auth/forgot-password')
def forgot_password():
    return _proxy_auth('POST', '/forgot-password', json=request.get_json(silent=True) or {})


@app.post('/api/auth/reset-password')
def reset_password():
    return _proxy_auth('POST', '/reset-password', json=request.get_json(silent=True) or {})


@app.get('/api/auth/reset-password/check')
def check_reset_token():
    token = request.args.get('token', '')
    return _proxy_auth('GET', f'/reset-password/check?token={token}')


# ---------------------------------------------------------------------------
# Admin — proxy das rotas administrativas do auth-service
# ---------------------------------------------------------------------------

@app.get('/api/admin/users')
def admin_list_users():
    """Lista todos os usuários. Exclusivo de admin (enforced no auth-service)."""
    return _proxy_auth('GET', '/admin/users')


@app.post('/api/admin/users/<int:target_id>/role')
def admin_change_role(target_id: int):
    """Promove ou rebaixa o papel de um usuário. Exclusivo de admin (enforced no auth-service)."""
    return _proxy_auth('POST', f'/admin/users/{target_id}/role', json=request.get_json(silent=True) or {})


@app.get('/api/admin/logs')
def admin_list_logs():
    """Retorna os últimos N eventos de auditoria. Exclusivo de admin.

    Query params:
        n     : int (padrão 50, máx 500) — quantos eventos retornar
        start : str                       — ID de início do range (XRANGE notation)
        end   : str                       — ID de fim do range

    Usuário comum tentando acessar recebe 403.
    """
    admin_user, err = require_role('admin')
    if err:
        # Loga tentativa de acesso negado (403)
        uid = None
        try:
            resp = _forward_to_auth('GET', '/me')
            if resp.status_code == 200:
                uid = resp.json().get('user', {}).get('id')
        except Exception:
            pass
        log_event('403_acesso_logs', usuario_id=uid, detalhe='tentativa de acesso ao log de auditoria')
        return err

    n = request.args.get('n', '50')
    start = request.args.get('start', '-')
    end = request.args.get('end', '+')
    cursor = request.args.get('cursor', '')
    acao = request.args.get('acao', '')
    target_usuario_id = request.args.get('usuario_id', '')
    data_inicio = request.args.get('data_inicio', '')
    data_fim = request.args.get('data_fim', '')

    params: dict[str, Any] = {'n': n, 'start': start, 'end': end}
    if cursor:
        params['cursor'] = cursor
    if acao:
        params['acao'] = acao
    if target_usuario_id:
        params['usuario_id'] = target_usuario_id
    if data_inicio:
        params['data_inicio'] = data_inicio
    if data_fim:
        params['data_fim'] = data_fim

    try:
        resp = requests.get(
            f'{log_service_url()}/logs',
            params=params,
            headers={'X-Internal-Token': internal_token()},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        # Enriquecimento com nome/email dos usuários
        users_map: dict[str, dict[str, str]] = {}
        try:
            users_resp = _forward_to_auth('GET', '/admin/users')
            if users_resp.status_code == 200:
                for u in users_resp.json().get('users', []):
                    users_map[str(u.get('id'))] = {
                        'nome': u.get('nome') or '',
                        'email': u.get('email') or '',
                    }
        except Exception as exc:
            app.logger.warning('Não foi possível obter lista de usuários para enriquecer logs: %s', exc)

        for log_entry in data.get('logs', []):
            uid_str = str(log_entry.get('usuario_id') or '')
            if uid_str in users_map:
                log_entry['usuario_nome'] = users_map[uid_str]['nome']
                log_entry['usuario_email'] = users_map[uid_str]['email']
            else:
                log_entry['usuario_nome'] = None
                log_entry['usuario_email'] = None

            # Normalização de detalhe caso seja JSON string
            raw_detalhe = log_entry.get('detalhe')
            if raw_detalhe and isinstance(raw_detalhe, str):
                trimmed = raw_detalhe.strip()
                if (trimmed.startswith('{') and trimmed.endswith('}')) or (trimmed.startswith('[') and trimmed.endswith(']')):
                    try:
                        log_entry['detalhe_json'] = _json.loads(trimmed)
                    except Exception:
                        log_entry['detalhe_json'] = None
                else:
                    log_entry['detalhe_json'] = None

        return jsonify(data)
    except requests.RequestException as exc:
        app.logger.error('log-service indisponível em admin_list_logs: %s', exc)
        return json_error('Serviço de log indisponível.', 503)


# ---------------------------------------------------------------------------
# Google OAuth — proxy para o auth-service
# ---------------------------------------------------------------------------

@app.get('/api/auth/google/url')
def google_auth_url():
    """Retorna a URL de autorização OAuth2 do Google para o frontend iniciar o fluxo."""
    return _proxy_auth('GET', '/auth/google/url')


@app.get('/api/auth/google/callback')
def google_auth_callback():
    """Recebe o callback do Google e repassa ao auth-service, que autentica e redireciona."""
    qs = request.query_string.decode('utf-8')
    return _proxy_auth('GET', f'/auth/google/callback?{qs}')


# ---------------------------------------------------------------------------
# Payment — proxy para o payment-service (assinatura Stripe)
# ---------------------------------------------------------------------------

def _forward_to_payment(method: str, path: str, **kwargs) -> requests.Response:
    """Encaminha uma requisição ao microsserviço de pagamentos."""
    url = f'{payment_service_url()}{path}'
    headers = kwargs.pop('headers', {})
    headers['X-Internal-Token'] = internal_token()
    client_ip = get_client_ip()
    headers['X-Forwarded-For'] = client_ip
    headers['X-Real-IP'] = client_ip
    return requests.request(method, url, headers=headers, timeout=30, **kwargs)


@app.get('/api/payment/config')
def payment_config():
    """Retorna configurações públicas do payment-service (publishable key)."""
    return jsonify({
        'stripe_publishable_key': os.getenv('STRIPE_PUBLISHABLE_KEY', ''),
        'payments_enabled': bool(os.getenv('STRIPE_PUBLISHABLE_KEY', '')),
    })


@app.post('/api/payment/checkout')
def payment_checkout():
    """Inicia Stripe Checkout Session. Requer autenticação e google_id."""
    user_data, err = require_role('usuario')
    if err:
        # Tenta pegar usuário mesmo sem role específica (inclusive admin testando fluxo)
        try:
            resp = _forward_to_auth('GET', '/me')
            if resp.status_code != 200:
                return json_error('Faça login para assinar.', 401)
            user_data = resp.json().get('user', {})
        except Exception:
            return json_error('Serviço de autenticação indisponível.', 503)

    user_id = user_data.get('id', 'anon')
    if not check_rate_limit(f'checkout:{user_id}', max_requests=5, window_seconds=60):
        return json_error('Muitas tentativas de checkout. Por favor, aguarde um minuto.', 429)

    google_id = user_data.get('google_id', '') if user_data else ''
    email = user_data.get('email', '') if user_data else ''

    if not google_id:
        return json_error(
            'Login com Google obrigatório para assinatura premium. '
            'Faça login com Google e tente novamente.', 403
        )

    try:
        resp = _forward_to_payment('POST', '/checkout', json={'google_id': google_id, 'email': email})
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as exc:
        app.logger.error('payment-service indisponível em checkout: %s', exc)
        return json_error('Serviço de pagamentos indisponível.', 503)


@app.post('/api/payment/portal')
def payment_portal():
    """Abre o Stripe Customer Portal para o usuário gerenciar ou cancelar."""
    try:
        resp = _forward_to_auth('GET', '/me')
        if resp.status_code != 200:
            return json_error('Faça login para continuar.', 401)
        user_data = resp.json().get('user', {})
    except Exception:
        return json_error('Serviço de autenticação indisponível.', 503)

    google_id = user_data.get('google_id', '') if user_data else ''
    if not google_id:
        return json_error('Login com Google obrigatório para gerenciar assinatura.', 403)

    try:
        resp = _forward_to_payment('POST', '/portal', json={'google_id': google_id})
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as exc:
        app.logger.error('payment-service indisponível em portal: %s', exc)
        return json_error('Serviço de pagamentos indisponível.', 503)


@app.post('/api/payment/webhook')
def payment_webhook():
    """Repassa webhooks da Stripe ao payment-service (preserva payload e headers)."""
    try:
        raw_body = request.get_data()
        sig_header = request.headers.get('Stripe-Signature', '')
        resp = _forward_to_payment(
            'POST',
            '/webhook',
            data=raw_body,
            headers={'Stripe-Signature': sig_header, 'Content-Type': 'application/json'},
        )
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as exc:
        app.logger.error('payment-service indisponível em webhook: %s', exc)
        return json_error('Serviço de pagamentos indisponível.', 503)


def _check_premium_entitlement() -> tuple[bool, dict[str, Any]]:
    """Consulta o payment-service e retorna (has_premium, entitlement_data).

    Administradores possuem acesso implícito ao conteúdo para fins de auditoria e suporte,
    mas os dados reais de assinatura Stripe do usuário são preservados se existirem.
    """
    try:
        resp_me = _forward_to_auth('GET', '/me')
        if resp_me.status_code != 200:
            return False, {}
        user_data = resp_me.json().get('user', {})
    except Exception:
        return False, {}

    is_admin = user_data.get('role') == 'admin'
    google_id = user_data.get('google_id', '') if user_data else ''
    stripe_entitlement: dict[str, Any] = {}

    if google_id:
        try:
            resp = _forward_to_payment('GET', f'/entitlement?google_id={google_id}')
            if resp.status_code == 200:
                stripe_entitlement = resp.json()
        except Exception as exc:
            app.logger.warning('payment-service indisponível em entitlement: %s', exc)

    if stripe_entitlement.get('has_premium'):
        return True, stripe_entitlement

    if is_admin:
        # Administrador tem acesso administrativo implícito
        return True, {
            'has_premium': True,
            'status': 'admin_access',
            'plan': 'Acesso Administrativo (Admin)',
            'is_admin': True,
            'stripe_status': stripe_entitlement.get('status', 'none'),
            'period_end': stripe_entitlement.get('period_end'),
        }

    return False, stripe_entitlement or {'has_premium': False, 'status': 'no_subscription'}


# ---------------------------------------------------------------------------
# Premium — benefícios verificáveis baseados na TMDB (Tom Hanks ID: 31)
# ---------------------------------------------------------------------------

@app.get('/api/payment/price')
def payment_price():
    """Retorna detalhes do plano consultando o payment-service (evita preço hardcoded)."""
    try:
        resp = _forward_to_payment('GET', '/plan-details')
        if resp.status_code == 200:
            return jsonify(resp.json())
    except Exception as exc:
        app.logger.warning('payment-service indisponível em payment_price: %s', exc)

    return jsonify({
        'name': 'Plano Premium',
        'currency': 'brl',
        'formatted_price': 'R$ 9,90',
        'interval': 'mês',
    })


@app.get('/api/premium/status')
def premium_status():
    """Retorna o status de assinatura premium do usuário autenticado."""
    user_id, err = require_login()
    if err:
        return err

    has_premium, entitlement = _check_premium_entitlement()
    return jsonify({
        'has_premium': has_premium,
        'entitlement': entitlement,
    })


@app.get('/api/premium/watchlist')
def premium_watchlist():
    """Filmografia por Direção e Produção de Tom Hanks (TMDB combined_credits).

    Retorna 402 se o usuário não possui acesso premium.
    """
    user_id, err = require_login()
    if err:
        return err

    has_premium, _ = _check_premium_entitlement()
    if not has_premium:
        return json_error(
            'Esta funcionalidade requer assinatura do Plano Premium.',
            402,
        )

    try:
        person_id = get_tom_hanks_person_id()
        payload = tmdb_request(f'/person/{person_id}/combined_credits')
        crew_credits = payload.get('crew', [])

        allowed_jobs = {'director', 'executive producer', 'producer'}
        seen_keys: set[tuple[int, str]] = set()
        result = []

        for item in sorted(
            crew_credits,
            key=lambda m: (m.get('release_date') or m.get('first_air_date') or '0000-00-00', m.get('popularity') or 0),
            reverse=True,
        ):
            item_id = int(item.get('id', 0))
            job = (item.get('job') or '').strip()
            if not item_id or job.lower() not in allowed_jobs:
                continue

            dedup_key = (item_id, job.lower())
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            release_date = item.get('release_date') or item.get('first_air_date') or ''
            year = release_date[:4] if len(release_date) >= 4 else 'Ano não informado'

            result.append({
                'tmdb_movie_id': item_id,
                'title': item.get('title') or item.get('name') or item.get('original_title') or 'Título indisponível',
                'overview': item.get('overview') or 'Sinopse indisponível no TMDB.',
                'poster_path': item.get('poster_path'),
                'poster_url': normalize_poster_path(item.get('poster_path')),
                'release_date': release_date,
                'year': year,
                'job': job,
                'department': item.get('department') or 'Produção/Direção',
                'media_type': item.get('media_type', 'movie'),
            })
            if len(result) >= 20:
                break

        log_event('premium_watchlist', usuario_id=user_id)
        return jsonify({
            'title': 'Filmografia por Direção e Produção',
            'movies': result,
            'count': len(result),
            'attribution': 'Fonte: TMDB · Atualizado dinamicamente',
        })
    except Exception as exc:
        app.logger.error('Falha ao buscar filmografia de direção/produção: %s', exc)
        return json_error('Não foi possível carregar a filmografia da TMDB.', 502)


@app.get('/api/premium/insights')
def premium_insights():
    """Retorna estatísticas e métricas de carreira calculadas a partir da TMDB.

    Métricas viáveis: quantidade por década e por função, nota média ponderada
    por vote_count, título mais popular da década, e dados de orçamento/receita.
    """
    user_id, err = require_login()
    if err:
        return err

    has_premium, _ = _check_premium_entitlement()
    if not has_premium:
        return json_error(
            'Esta funcionalidade requer assinatura do Plano Premium.',
            402,
        )

    try:
        from datetime import datetime
        person_id = get_tom_hanks_person_id()
        credits_payload = tmdb_request(f'/person/{person_id}/combined_credits')
        cast_list = credits_payload.get('cast', [])
        crew_list = credits_payload.get('crew', [])

        all_items = cast_list + crew_list

        # 1. Menor release_date para calcular dinamicamente os anos de carreira
        valid_dates = []
        for c in all_items:
            d = c.get('release_date') or c.get('first_air_date') or ''
            if len(d) >= 4 and d[:4].isdigit():
                valid_dates.append(int(d[:4]))

        start_year = min(valid_dates) if valid_dates else 1980
        current_year = datetime.now().year
        career_years = current_year - start_year

        # 2. Títulos por década e por função
        movies_by_decade: dict[str, int] = {}
        decade_roles: dict[str, dict[str, int]] = {}
        decade_top_movie: dict[str, dict[str, Any]] = {}

        # 3. Média ponderada por vote_count (para títulos com mínimo de 100 votos)
        weighted_vote_sum = 0.0
        total_votes = 0
        min_votes_threshold = 100

        seen_title_ids = set()

        for c in cast_list:
            cid = c.get('id')
            if not cid or cid in seen_title_ids:
                continue
            seen_title_ids.add(cid)

            d = c.get('release_date') or c.get('first_air_date') or ''
            if len(d) >= 4 and d[:4].isdigit():
                year = int(d[:4])
                decade = f'{(year // 10) * 10}s'
                movies_by_decade[decade] = movies_by_decade.get(decade, 0) + 1

                if decade not in decade_roles:
                    decade_roles[decade] = {'Ator': 0, 'Diretor': 0, 'Produtor': 0}
                decade_roles[decade]['Ator'] += 1

                # Título mais popular da década
                pop = float(c.get('popularity') or 0)
                curr_top = decade_top_movie.get(decade)
                if not curr_top or pop > curr_top.get('popularity', 0):
                    decade_top_movie[decade] = {
                        'title': c.get('title') or c.get('name') or 'Título indisponível',
                        'popularity': round(pop, 1),
                        'year': year,
                        'poster_url': normalize_poster_path(c.get('poster_path')),
                    }

            # Média ponderada
            va = float(c.get('vote_average') or 0)
            vc = int(c.get('vote_count') or 0)
            if va > 0 and vc >= min_votes_threshold:
                weighted_vote_sum += (va * vc)
                total_votes += vc

        for cr in crew_list:
            job = (cr.get('job') or '').lower()
            d = cr.get('release_date') or cr.get('first_air_date') or ''
            if len(d) >= 4 and d[:4].isdigit():
                year = int(d[:4])
                decade = f'{(year // 10) * 10}s'
                if decade not in decade_roles:
                    decade_roles[decade] = {'Ator': 0, 'Diretor': 0, 'Produtor': 0}
                if 'director' in job:
                    decade_roles[decade]['Diretor'] += 1
                elif 'producer' in job:
                    decade_roles[decade]['Produtor'] += 1

        weighted_average = round(weighted_vote_sum / total_votes, 2) if total_votes > 0 else 7.85

        # 4. Amostra de bilheteria e orçamento de clássicos consagrados (com cache Redis individual)
        # Nota: TMDB frequentemente retorna 0 para revenue/budget, portanto 0 é tratado estritamente como dado indisponível!
        sample_movie_ids = [13, 857, 8587]  # Forrest Gump, Saving Private Ryan, The Lion King / Cast Away
        financial_highlights = []

        for mid in sample_movie_ids:
            try:
                m_details = tmdb_request(f'/movie/{mid}')
                raw_rev = m_details.get('revenue') or 0
                raw_bud = m_details.get('budget') or 0

                revenue_str = f"${raw_rev:,}" if raw_rev > 0 else 'Dado indisponível'
                budget_str = f"${raw_bud:,}" if raw_bud > 0 else 'Dado indisponível'

                financial_highlights.append({
                    'title': m_details.get('title') or 'Título',
                    'year': (m_details.get('release_date') or '')[:4],
                    'revenue': revenue_str,
                    'budget': budget_str,
                    'poster_url': normalize_poster_path(m_details.get('poster_path')),
                })
            except Exception:
                continue

        # Ordenar décadas cronologicamente
        sorted_decades = {k: movies_by_decade[k] for k in sorted(movies_by_decade.keys())}
        sorted_roles = {k: decade_roles[k] for k in sorted(decade_roles.keys())}

        current_date_str = datetime.now().strftime('%d/%m/%Y')
        attribution_text = f"Fonte: TMDB · atualizado em {current_date_str}"

        log_event('premium_insights', usuario_id=user_id)
        return jsonify({
            'total_movies': len(seen_title_ids),
            'career_start_year': start_year,
            'career_years': career_years,
            'career_headline': f'Carreira de {career_years}+ anos no cinema e na TV',
            'movies_by_decade': sorted_decades,
            'roles_by_decade': sorted_roles,
            'weighted_average_rating': weighted_average,
            'min_votes_filter': min_votes_threshold,
            'top_movie_by_decade': decade_top_movie,
            'financial_highlights': financial_highlights,
            'attribution': attribution_text,
        })
    except Exception as exc:
        app.logger.error('Falha ao calcular insights premium: %s', exc)
        return json_error('Não foi possível calcular os insights analíticos.', 502)


@app.get('/api/premium/videos')
def premium_videos():
    """Retorna vídeos de bastidores (Behind the Scenes e Featurettes) da TMDB.

    Conforme conformidade, não utiliza a palavra 'exclusivo', pois dados TMDB são públicos.
    """
    user_id, err = require_login()
    if err:
        return err

    has_premium, _ = _check_premium_entitlement()
    if not has_premium:
        return json_error('Funcionalidade disponível no Plano Premium.', 402)

    try:
        # Busca bastidores dos filmes mais aclamados
        movies_to_check = [13, 857, 597, 8587]  # Forrest Gump, Saving Private Ryan, etc.
        videos = []
        for mid in movies_to_check:
            try:
                m_info = tmdb_request(f'/movie/{mid}')
                m_vids = tmdb_request(f'/movie/{mid}/videos')
                for v in m_vids.get('results', []):
                    v_type = v.get('type')
                    if v_type in ('Behind the Scenes', 'Featurette'):
                        videos.append({
                            'movie_title': m_info.get('title'),
                            'name': v.get('name'),
                            'type': v_type,
                            'site': v.get('site'),
                            'key': v.get('key'),
                            'url': f"https://www.youtube.com/watch?v={v.get('key')}" if v.get('site') == 'YouTube' else None,
                        })
                        if len(videos) >= 6:
                            break
            except Exception:
                continue

        log_event('premium_videos', usuario_id=user_id)
        return jsonify({
            'videos': videos,
            'count': len(videos),
            'attribution': 'Fonte: TMDB · Conteúdo de bastidores e featurettes oficiais',
        })
    except Exception as exc:
        app.logger.error('Falha ao buscar bastidores da TMDB: %s', exc)
        return json_error('Não foi possível carregar os vídeos de bastidores.', 502)


# ---------------------------------------------------------------------------
# Admin Infraestrutura — status de todos os serviços, Redis, Swagger links
# ---------------------------------------------------------------------------

@app.get('/api/admin/infra/health')
def admin_infra_health():
    """Retorna o status detalhado de todos os serviços com contrato padronizado. Exclusivo de admin."""
    _, err = require_role('admin')
    if err:
        return err

    from datetime import datetime, timezone
    services: list[dict[str, Any]] = []

    def _check(name: str, url: str, timeout: int = 3) -> dict[str, Any]:
        t0 = _time.monotonic()
        try:
            resp = requests.get(url, timeout=timeout)
            latency_ms = round((_time.monotonic() - t0) * 1000, 2)
            is_json = resp.headers.get('content-type', '').startswith('application/json')
            body = resp.json() if is_json else {}
            svc_status = body.get('status') or ('healthy' if resp.status_code == 200 else 'degraded')
            return {
                'name': name,
                'status': svc_status,
                'http_status': resp.status_code,
                'latency_ms': latency_ms,
                'version': body.get('version', '1.0.0'),
                'uptime_seconds': body.get('uptime_seconds'),
                'timestamp': body.get('timestamp') or datetime.now(timezone.utc).isoformat(),
                'dependencies': body.get('dependencies', {}),
                'details': body,
                'error': None if resp.status_code == 200 else f"HTTP {resp.status_code}",
            }
        except Exception as exc:
            latency_ms = round((_time.monotonic() - t0) * 1000, 2)
            return {
                'name': name,
                'status': 'unreachable',
                'http_status': None,
                'latency_ms': latency_ms,
                'version': '1.0.0',
                'uptime_seconds': None,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'dependencies': {},
                'details': {},
                'error': f"Inacessível: {exc}",
            }

    # O app-gateway NUNCA deve fazer uma requisição HTTP circular para si mesmo,
    # pois com worker síncrono isso causa deadlock e timeout de 3s, fazendo com que
    # o gateway apareça falsamente como 'Indisponível/Falha' no painel.
    # Em vez disso, verificamos a saúde dos componentes locais do gateway diretamente em processo.
    t0_gateway = _time.monotonic()
    db_ok = False
    db_err = None
    minio_ok = False
    minio_err = None

    try:
        with session_scope() as db:
            db.execute(select(1))
        db_ok = True
    except Exception as exc:
        db_err = str(exc)

    try:
        minio_ok = minio_is_ready()
        if not minio_ok:
            minio_err = "Object storage MinIO indisponível ou credenciais ausentes"
    except Exception as exc:
        minio_err = str(exc)

    gateway_latency = round((_time.monotonic() - t0_gateway) * 1000, 2)
    gateway_status = 'healthy' if (db_ok and minio_ok) else 'degraded' if db_ok else 'unhealthy'

    services.append({
        'name': 'app-gateway',
        'status': gateway_status,
        'http_status': 200,
        'latency_ms': gateway_latency,
        'version': '1.0.0',
        'uptime_seconds': round(_time.time() - START_TIME, 1),
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'dependencies': {
            'database': {
                'status': 'connected' if db_ok else 'disconnected',
                'error': db_err,
            },
            'minio': {
                'status': 'connected' if minio_ok else 'disconnected',
                'error': minio_err,
            },
        },
        'details': {
            'status': gateway_status,
            'service': 'app-gateway',
            'role': 'Ponto de Entrada e Catálogo',
        },
        'error': None if gateway_status == 'healthy' else ("MinIO degradado" if db_ok else "Banco de dados indisponível"),
    })

    services.append(_check('auth-service', f'{auth_service_url()}/health'))
    services.append(_check('log-service', f'{log_service_url()}/health'))
    services.append(_check('payment-service', f'{payment_service_url()}/health'))

    all_healthy = all(s['status'] == 'healthy' for s in services)
    return jsonify({
        'overall': 'healthy' if all_healthy else 'degraded',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'services': services,
    })


@app.get('/api/admin/infra/redis')
def admin_infra_redis():
    """Retorna informações completas do Redis: conexões ativas, memória em MB, uptime e ops/s. Exclusivo de admin."""
    _, err = require_role('admin')
    if err:
        return err

    try:
        r = get_redis()
        r.ping()

        info = r.info('server')
        clients = r.info('clients')
        memory = r.info('memory')
        stats = r.info('stats')
        stream_info: dict[str, Any] = {}

        try:
            stream_len = r.xlen('audit:logs')
            stream_info = {
                'stream_key': 'audit:logs',
                'length': stream_len,
            }
        except Exception as exc:
            stream_info = {'stream_key': 'audit:logs', 'length': None, 'error': f'Stream indisponível: {exc}'}

        used_memory_bytes = memory.get('used_memory', 0)
        used_memory_mb = round(used_memory_bytes / (1024 * 1024), 2)
        connected_clients = clients.get('connected_clients', 1)
        uptime_seconds = info.get('uptime_in_seconds', 0)
        instantaneous_ops = stats.get('instantaneous_ops_per_sec', 0)

        return jsonify({
            'status': 'connected',
            'version': info.get('redis_version', '7.x'),
            'uptime_seconds': uptime_seconds,
            'connected_clients': max(1, connected_clients),
            'used_memory_bytes': used_memory_bytes,
            'used_memory_mb': used_memory_mb,
            'used_memory_human': f"{used_memory_mb} MB",
            'maxmemory_human': memory.get('maxmemory_human') or 'sem limite',
            'ops_per_sec': instantaneous_ops,
            'streams': [stream_info],
        })
    except Exception as exc:
        app.logger.error('Erro ao conectar ao Redis em admin_infra_redis: %s', exc)
        return jsonify({'status': 'disconnected', 'error': str(exc)}), 503


@app.get('/api/admin/infra/swagger-links')
def admin_infra_swagger_links():
    """Retorna links de Swagger/OpenAPI de todos os serviços. Exclusivo de admin."""
    _, err = require_role('admin')
    if err:
        return err

    base = request.host_url.rstrip('/')
    return jsonify({
        'services': [
            {
                'name': 'Catálogo (Gateway)',
                'swagger_ui': f'{base}/apidocs',
                'openapi_json': f'{base}/api/docs/openapi.json',
            },
            {
                'name': 'auth-service',
                'swagger_ui': f'{auth_service_url()}/apidocs',
                'openapi_json': f'{base}/api/docs/auth/openapi.json',
            },
            {
                'name': 'log-service',
                'swagger_ui': f'{log_service_url()}/apidocs',
                'openapi_json': f'{base}/api/docs/log/openapi.json',
            },
            {
                'name': 'payment-service',
                'swagger_ui': f'{payment_service_url()}/apidocs',
                'openapi_json': f'{base}/api/docs/payment/openapi.json',
            },
        ]
    })


@app.get('/api/docs/payment/openapi.json')
def payment_openapi_json():
    """Proxy para a especificação OpenAPI 3.0 do payment-service."""
    try:
        resp = requests.get(f'{payment_service_url()}/api/docs/openapi.json', timeout=2)
        if resp.status_code == 200:
            return Response(resp.content, content_type='application/json; charset=utf-8')
    except Exception as exc:
        app.logger.warning('Falha ao obter especificação OpenAPI do payment-service: %s', exc)

    fallback = {
        "openapi": "3.0.3",
        "info": {
            "title": "payment-service (Indisponível)",
            "description": "O microsserviço de pagamentos está temporariamente inacessível na rede Docker.",
            "version": "1.0.0"
        },
        "paths": {}
    }
    return jsonify(fallback)



@app.get('/api/profile/<int:user_id>')
def get_user_profile(user_id: int):
    """Retorna os dados do perfil do usuário e a lista de filmes favoritados por ele."""
    try:
        resp = _forward_to_auth('GET', f'/users/{user_id}')
        if resp.status_code != 200:
            return _proxy_auth('GET', f'/users/{user_id}')
        user_data = resp.json().get('user', {})
    except Exception as exc:
        app.logger.error('Erro ao buscar perfil no auth-service: %s', exc)
        return json_error('Serviço de autenticação indisponível.', 503)

    # Busca os favoritos do usuário no MariaDB local
    with session_scope() as db:
        fav_rows = db.scalars(
            select(Favorite).where(Favorite.usuario_id == user_id).order_by(Favorite.criado_em.desc())
        ).all()
        favorites = [
            {
                'id': int(f.id),
                'tmdb_movie_id': int(f.tmdb_movie_id),
                'title': f.titulo,
                'poster_path': f.poster_path,
                'poster_url': normalize_poster_path(f.poster_path),
                'criado_em': f.criado_em.isoformat() if hasattr(f.criado_em, 'isoformat') else f.criado_em,
            }
            for f in fav_rows
        ]

    return jsonify({
        'user': user_data,
        'favorites': favorites,
        'favorite_count': len(favorites),
    })


@app.put('/api/profile/<int:user_id>')
def update_user_profile(user_id: int):
    """Atualiza o perfil do usuário (nome e bio). Regra 403 tratada no auth-service."""
    return _proxy_auth('PUT', f'/users/{user_id}', json=request.get_json(silent=True) or {})


@app.post('/api/profile/<int:user_id>/avatar')
def upload_user_avatar(user_id: int):
    """Realiza upload de imagem de perfil do usuário. Regra 403 tratada no auth-service."""
    if 'avatar' not in request.files and 'file' not in request.files:
        return json_error('Nenhum arquivo enviado.', 400)

    file_obj = request.files.get('avatar') or request.files.get('file')
    if not file_obj or not file_obj.filename:
        return json_error('Arquivo inválido.', 400)

    files = {'avatar': (file_obj.filename, file_obj.stream, file_obj.content_type or 'image/jpeg')}
    return _proxy_auth('POST', f'/users/{user_id}/avatar', files=files)


@app.get('/api/profile/avatar/<path:key>')
def serve_user_avatar(key: str):
    """Serve a imagem de avatar do MinIO diretamente aos clientes."""
    from minio import Minio
    raw_endpoint = os.getenv('MINIO_ENDPOINT', 'minio:9000')
    access_key = os.getenv('MINIO_ACCESS_KEY', '')
    secret_key = os.getenv('MINIO_SECRET_KEY', '')
    bucket_name = os.getenv('MINIO_BUCKET_NAME', 'tomhanks-avatars')

    if not access_key or not secret_key:
        return json_error('Serviço de armazenamento não configurado.', 503)

    endpoint = raw_endpoint.split('://')[-1] if '://' in raw_endpoint else raw_endpoint
    try:
        client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=False)
        content_type = 'image/png'
        key_lower = key.lower()
        if key_lower.endswith(('.jpg', '.jpeg')):
            content_type = 'image/jpeg'
        elif key_lower.endswith('.webp'):
            content_type = 'image/webp'
        elif key_lower.endswith('.gif'):
            content_type = 'image/gif'

        with client.get_object(bucket_name, key) as response:
            data = response.read()

        return Response(data, content_type=content_type)
    except Exception as exc:
        app.logger.warning('Avatar key=%s não encontrado no MinIO: %s', key, exc)
        return json_error('Avatar não encontrado.', 404)


# ---------------------------------------------------------------------------
# Documentação Swagger / OpenAPI 3.0 (Atividade Extra)
# ---------------------------------------------------------------------------

@app.get('/api/docs/openapi.json')
def openapi_json():
    """Retorna a especificação OpenAPI 3.0 em formato JSON."""
    from backend.swagger_spec import get_openapi_json
    return Response(get_openapi_json(), content_type='application/json; charset=utf-8')


@app.get('/api/docs/openapi.yaml')
def openapi_yaml():
    """Retorna a especificação OpenAPI 3.0 em formato YAML."""
    from backend.swagger_spec import get_openapi_yaml
    return Response(get_openapi_yaml(), content_type='text/yaml; charset=utf-8')


@app.get('/api/docs/auth/openapi.json')
def auth_openapi_json():
    """Proxy para a especificação OpenAPI 3.0 do auth-service."""
    try:
        resp = requests.get(f'{auth_service_url()}/api/docs/openapi.json', timeout=2)
        if resp.status_code == 200:
            return Response(resp.content, content_type='application/json; charset=utf-8')
    except Exception as exc:
        app.logger.warning('Falha ao obter especificação OpenAPI do auth-service: %s', exc)

    fallback = {
        "openapi": "3.0.3",
        "info": {
            "title": "auth-service (Indisponível)",
            "description": "O microsserviço de autenticação está temporariamente inacessível na rede Docker.",
            "version": "1.0.0"
        },
        "paths": {}
    }
    return jsonify(fallback)


@app.get('/api/docs/log/openapi.json')
def log_openapi_json():
    """Proxy para a especificação OpenAPI 3.0 do log-service."""
    try:
        resp = requests.get(f'{log_service_url()}/api/docs/openapi.json', timeout=2)
        if resp.status_code == 200:
            return Response(resp.content, content_type='application/json; charset=utf-8')
    except Exception as exc:
        app.logger.warning('Falha ao obter especificação OpenAPI do log-service: %s', exc)

    fallback = {
        "openapi": "3.0.3",
        "info": {
            "title": "log-service (Indisponível)",
            "description": "O microsserviço de auditoria (log-service) está temporariamente inacessível na rede Docker.",
            "version": "1.0.0"
        },
        "paths": {}
    }
    return jsonify(fallback)


@app.get('/apidocs')
@app.get('/docs')
def swagger_ui():
    """Renderiza a interface interativa do Swagger UI integrada à aplicação com seletor de serviços."""
    html_content = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>Documentação Swagger / OpenAPI — Catálogo Tom Hanks</title>
  <link rel="stylesheet" type="text/css" href="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/5.11.0/swagger-ui.min.css" />
  <style>
    html { box-sizing: border-box; overflow-y: scroll; }
    *, *:before, *:after { box-sizing: inherit; }
    body { margin:0; background: #0f172a; color: #f8fafc; font-family: sans-serif; }
    .swagger-ui .topbar { background-color: #1e293b; border-bottom: 2px solid #e94560; }
    .swagger-ui .info .title { color: #f8fafc; }
  </style>
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/5.11.0/swagger-ui-bundle.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/5.11.0/swagger-ui-standalone-preset.min.js"></script>
  <script>
    window.onload = function() {
      const ui = SwaggerUIBundle({
        urls: [
          { url: "/api/docs/openapi.json", name: "Catálogo (Gateway)" },
          { url: "/api/docs/auth/openapi.json", name: "auth-service" },
          { url: "/api/docs/log/openapi.json", name: "log-service" },
          { url: "/api/docs/payment/openapi.json", name: "payment-service" }
        ],
        "urls.primaryName": "Catálogo (Gateway)",
        dom_id: '#swagger-ui',
        deepLinking: true,
        presets: [
          SwaggerUIBundle.presets.apis,
          SwaggerUIStandalonePreset
        ],
        plugins: [
          SwaggerUIBundle.plugins.DownloadUrl
        ],
        layout: "StandaloneLayout"
      });
      window.ui = ui;
    };
  </script>
</body>
</html>
"""
    return Response(html_content, content_type='text/html; charset=utf-8')


# ---------------------------------------------------------------------------
# Catálogo
# ---------------------------------------------------------------------------

def load_user_state(db, user_id: int) -> tuple[set[int], list[dict[str, Any]]]:
    favorite_ids = set(
        db.scalars(
            select(Favorite.tmdb_movie_id).where(Favorite.usuario_id == user_id).order_by(Favorite.criado_em.desc())
        ).all()
    )
    comment_rows = db.scalars(
        select(Comment).where(Comment.usuario_id == user_id).order_by(Comment.criado_em.desc(), Comment.id.desc())
    ).all()
    comments = [
        {
            'id': int(row.id),
            'tmdb_movie_id': int(row.tmdb_movie_id),
            'texto': row.texto,
            'criado_em': row.criado_em.isoformat() if hasattr(row.criado_em, 'isoformat') else row.criado_em,
        }
        for row in comment_rows
    ]
    return favorite_ids, comments


@app.get('/api/catalog')
def catalog():
    user_id, error = require_login()
    if error:
        return error

    with session_scope() as db:
        favorite_ids, comments = load_user_state(db, user_id)
        try:
            tmdb_movies = get_tom_hanks_catalog()
            catalog_warning = None
        except Exception as exc:
            if _LAST_KNOWN_CATALOG:
                tmdb_movies = _catalog_copy(_LAST_KNOWN_CATALOG)
                catalog_warning = 'A TMDB ficou indisponível; exibindo o último catálogo carregado.'
                app.logger.warning('Servindo catálogo em cache após falha na TMDB: %s', exc)
            else:
                tmdb_movies = []
                catalog_warning = 'Não foi possível carregar o catálogo da TMDB neste momento.'
                app.logger.exception('Falha ao carregar catálogo da TMDB.')

        movies = [serialize_movie(movie, favorite_ids, comments) for movie in tmdb_movies]
        favorites = [movie for movie in movies if movie['is_favorite']]
        payload = {
            'user_id': user_id,
            'movies': movies,
            'favorites': favorites,
            'stats': {
                'favorite_count': len(favorites),
                'comment_count': len(comments),
            },
        }
        if catalog_warning:
            payload['warning'] = catalog_warning
        return jsonify(payload)


# ---------------------------------------------------------------------------
# Favoritos
# ---------------------------------------------------------------------------

@app.get('/api/favorites')
def favorites():
    user_id, error = require_login()
    if error:
        return error

    with session_scope() as db:
        rows = db.scalars(
            select(Favorite).where(Favorite.usuario_id == user_id).order_by(Favorite.criado_em.desc())
        ).all()
        payload = []
        for row in rows:
            payload.append(
                {
                    'id': int(row.id),
                    'tmdb_movie_id': int(row.tmdb_movie_id),
                    'title': row.titulo,
                    'poster_path': row.poster_path,
                    'poster_url': normalize_poster_path(row.poster_path),
                    'criado_em': row.criado_em.isoformat() if hasattr(row.criado_em, 'isoformat') else row.criado_em,
                }
            )
        return jsonify({'favorites': payload})


@app.post('/api/favorites')
def create_favorite():
    user_id, error = require_login()
    if error:
        return error

    if not check_rate_limit(f'fav:{user_id}', max_requests=30, window_seconds=60):
        return json_error('Muitas operações de favoritos. Por favor, aguarde alguns instantes.', 429)

    payload = request.get_json(silent=True) or {}
    movie_id = payload.get('tmdb_movie_id')
    if movie_id is None:
        return json_error('Informe o filme a favoritar.')

    try:
        movie_id = int(movie_id)
    except (TypeError, ValueError):
        return json_error('tmdb_movie_id inválido.')

    try:
        movie = get_movie_details(movie_id)
    except Exception as exc:
        return json_error(f'Não foi possível carregar o filme da TMDB: {exc}', 502)

    try:
        with session_scope() as db:
            favorite = db.scalar(
                select(Favorite).where(Favorite.usuario_id == user_id, Favorite.tmdb_movie_id == movie_id)
            )
            is_new = favorite is None
            if is_new:
                favorite = Favorite(
                    usuario_id=user_id,
                    tmdb_movie_id=movie_id,
                    titulo=movie['title'],
                    poster_path=movie.get('poster_path'),
                )
                db.add(favorite)
                db.flush()
                # Só grava evento de auditoria quando a ação efetivamente adicionar novo favorito
                log_event(
                    'favoritar',
                    usuario_id=user_id,
                    detalhe={'movie_id': movie_id, 'title': movie['title'], 'action': 'adicionar'},
                )
                status_code = 201
            else:
                # Idempotente: favorito já cadastrado, sincroniza detalhes sem duplicar auditoria
                favorite.titulo = movie['title']
                favorite.poster_path = movie.get('poster_path')
                status_code = 200

            return jsonify(
                {
                    'ok': True,
                    'already_favorite': not is_new,
                    'favorite': {
                        'tmdb_movie_id': movie_id,
                        'title': movie['title'],
                        'poster_path': movie.get('poster_path'),
                        'poster_url': movie.get('poster_url'),
                    },
                }
            ), status_code
    except Exception as exc:
        app.logger.warning('Erro ao processar favorito (possível concorrência): %s', exc)
        return jsonify({
            'ok': True,
            'already_favorite': True,
            'favorite': {
                'tmdb_movie_id': movie_id,
                'title': movie['title'],
                'poster_path': movie.get('poster_path'),
                'poster_url': movie.get('poster_url'),
            },
        }), 200


@app.delete('/api/favorites/<int:movie_id>')
def delete_favorite(movie_id: int):
    user_id, error = require_login()
    if error:
        return error

    if not check_rate_limit(f'fav:{user_id}', max_requests=30, window_seconds=60):
        return json_error('Muitas operações de favoritos. Por favor, aguarde alguns instantes.', 429)

    with session_scope() as db:
        result = db.execute(
            delete(Favorite).where(Favorite.usuario_id == user_id, Favorite.tmdb_movie_id == movie_id)
        )
        deleted = result.rowcount > 0
        if deleted:
            log_event(
                'desfavoritar',
                usuario_id=user_id,
                detalhe={'movie_id': movie_id, 'action': 'remover'},
            )
        return jsonify({'ok': True, 'deleted': deleted})


# ---------------------------------------------------------------------------
# Comentários
# ---------------------------------------------------------------------------

@app.get('/api/comments')
def list_comments():
    user_id, error = require_login()
    if error:
        return error

    movie_id_raw = request.args.get('movie_id')
    with session_scope() as db:
        if movie_id_raw:
            try:
                movie_id = int(movie_id_raw)
            except (TypeError, ValueError):
                return json_error('movie_id inválido.')
            rows = db.scalars(
                select(Comment)
                .where(Comment.usuario_id == user_id, Comment.tmdb_movie_id == movie_id)
                .order_by(Comment.criado_em.desc(), Comment.id.desc())
            ).all()
        else:
            rows = db.scalars(
                select(Comment).where(Comment.usuario_id == user_id).order_by(Comment.criado_em.desc(), Comment.id.desc())
            ).all()

        comments = [
            {
                'id': int(row.id),
                'tmdb_movie_id': int(row.tmdb_movie_id),
                'texto': row.texto,
                'criado_em': row.criado_em.isoformat() if hasattr(row.criado_em, 'isoformat') else row.criado_em,
            }
            for row in rows
        ]
        return jsonify({'comments': comments})


@app.post('/api/comments')
def create_comment():
    user_id, error = require_login()
    if error:
        return error

    payload = request.get_json(silent=True) or {}
    texto = str(payload.get('texto', '')).strip()
    movie_id = payload.get('tmdb_movie_id')
    if movie_id is None:
        return json_error('Informe o filme comentado.')

    try:
        movie_id = int(movie_id)
    except (TypeError, ValueError):
        return json_error('tmdb_movie_id inválido.')

    if not texto:
        return json_error('Escreva um comentário antes de salvar.')

    if len(texto) > 4000:
        return json_error('O comentário é muito longo.')

    with session_scope() as db:
        comment = Comment(usuario_id=user_id, tmdb_movie_id=movie_id, texto=texto)
        db.add(comment)
        db.flush()
        db.refresh(comment)
        log_event('comentar', usuario_id=user_id, detalhe={'movie_id': movie_id, 'comment_id': int(comment.id)})
        return jsonify(
            {
                'ok': True,
                'comment': {
                    'id': int(comment.id),
                    'tmdb_movie_id': movie_id,
                    'texto': texto,
                },
            }
        ), 201


@app.delete('/api/comments/<int:comment_id>')
def delete_comment(comment_id: int):
    user_id, error = require_login()
    if error:
        return error

    # Verifica se o usuário é admin (enforcement no servidor, não no cliente)
    admin_user, _ = require_role('admin')
    is_admin = admin_user is not None

    with session_scope() as db:
        if is_admin:
            # Admin pode apagar comentários de qualquer usuário (moderação)
            result = db.execute(delete(Comment).where(Comment.id == comment_id))
        else:
            # Usuário comum só pode apagar os próprios comentários
            result = db.execute(delete(Comment).where(Comment.id == comment_id, Comment.usuario_id == user_id))

        deleted = result.rowcount > 0
        if not deleted and not is_admin:
            # Se não deletou nada e não é admin, pode ser que o comentário pertence a outro usuário
            comment_exists = db.scalar(select(Comment).where(Comment.id == comment_id))
            if comment_exists:
                log_event(
                    '403_apagar_comentario',
                    usuario_id=user_id,
                    detalhe={'comment_id': comment_id, 'motivo': 'sem_permissao'},
                )
                return json_error('Sem permissão para apagar este comentário.', 403)

        acao = 'moderacao_apagar_comentario' if is_admin else 'apagar_comentario'
        log_event(acao, usuario_id=user_id, detalhe={'comment_id': comment_id, 'deleted': deleted})
        return jsonify({'ok': True, 'deleted': deleted})


# ---------------------------------------------------------------------------
# Frontend estático
# ---------------------------------------------------------------------------

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path: str):
    if path.startswith('api/'):
        return json_error('Not found', 404)

    if path:
        candidate = STATIC_DIR / path
        if candidate.is_file():
            return send_from_directory(STATIC_DIR, path)

    index_file = STATIC_DIR / 'index.html'
    if index_file.is_file():
        return send_from_directory(STATIC_DIR, 'index.html')

    return jsonify(
        {
            'message': 'Frontend build not found. Build the Angular app into backend/static.',
            'hint': 'Use the Dockerfile or copy the Angular browser dist folder to backend/static.',
        }
    )


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '5000')), debug=os.getenv('FLASK_DEBUG', '0') == '1')
