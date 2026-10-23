from __future__ import annotations

import os
import time

import redis
from flask import Flask, jsonify, request
from prometheus_flask_exporter import PrometheusMetrics

app = Flask(__name__)
metrics = PrometheusMetrics(app)

REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379/0')
INTERNAL_TOKEN = os.getenv('INTERNAL_TOKEN', '')
LOG_STREAM_KEY = 'audit:logs'

# Quantidade máxima de entradas no stream (trim automático)
MAX_LOG_ENTRIES = int(os.getenv('MAX_LOG_ENTRIES', '10000'))


START_TIME = time.time()
_redis_pool: redis.ConnectionPool | None = None


def get_redis() -> redis.Redis:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = redis.ConnectionPool.from_url(
            REDIS_URL,
            decode_responses=True,
            max_connections=20,
        )
    return redis.Redis(connection_pool=_redis_pool)


def json_error(message: str, status: int = 400):
    return jsonify({'error': message}), status


def require_internal_token():
    """Verifica se a requisição vem de um serviço interno."""
    token = request.headers.get('X-Internal-Token', '')
    if not INTERNAL_TOKEN or token != INTERNAL_TOKEN:
        return json_error('Acesso não autorizado.', 403)
    return None


# ---------------------------------------------------------------------------
# Documentação Swagger / OpenAPI 3.0 — log-service (Restrito à rede interna)
# ---------------------------------------------------------------------------

@app.get('/api/docs/openapi.json')
def openapi_json():
    """Retorna a especificação OpenAPI 3.0 do log-service em JSON."""
    err = require_internal_token()
    if err:
        return err
    from flask import Response
    from log_service.swagger_spec import get_openapi_json
    return Response(get_openapi_json(), content_type='application/json; charset=utf-8')


@app.get('/api/docs/openapi.yaml')
def openapi_yaml():
    """Retorna a especificação OpenAPI 3.0 do log-service em YAML."""
    err = require_internal_token()
    if err:
        return err
    from flask import Response
    from log_service.swagger_spec import get_openapi_yaml
    return Response(get_openapi_yaml(), content_type='text/yaml; charset=utf-8')


@app.get('/apidocs')
@app.get('/docs')
def swagger_ui():
    """Renderiza o Swagger UI para o log-service (Restrito)."""
    err = require_internal_token()
    if err:
        return err
    from flask import Response
    html_content = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>log-service — Documentação OpenAPI</title>
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
        url: "/api/docs/openapi.json",
        dom_id: '#swagger-ui',
        deepLinking: true,
        presets: [SwaggerUIBundle.presets.apis, SwaggerUIStandalonePreset],
        plugins: [SwaggerUIBundle.plugins.DownloadUrl],
        layout: "StandaloneLayout"
      });
      window.ui = ui;
    };
  </script>
</body>
</html>"""
    return Response(html_content, content_type='text/html; charset=utf-8')


# ---------------------------------------------------------------------------
# Health & Readiness (Contrato Padronizado)
# ---------------------------------------------------------------------------

@app.get('/health')
def health():
    from datetime import datetime, timezone
    t0 = time.monotonic()
    redis_ok = False
    redis_err = None
    try:
        r = get_redis()
        r.ping()
        redis_ok = True
    except Exception as exc:
        redis_err = str(exc)
        app.logger.error('Redis indisponível em healthcheck: %s', exc)

    latency_ms = round((time.monotonic() - t0) * 1000, 2)
    healthy = redis_ok
    status_code = 200 if healthy else 503

    payload = {
        'status': 'healthy' if healthy else 'unhealthy',
        'service': 'log-service',
        'version': '1.0.0',
        'uptime_seconds': round(time.time() - START_TIME, 1),
        'latency_ms': latency_ms,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'dependencies': {
            'redis': {
                'status': 'connected' if redis_ok else 'disconnected',
                'error': redis_err,
            }
        }
    }
    return jsonify(payload), status_code


# ---------------------------------------------------------------------------
# Gravar evento de auditoria (uso interno)
# ---------------------------------------------------------------------------

@app.post('/log')
def record_log():
    """Grava um evento de auditoria no Redis Stream.

    Payload esperado (JSON):
        usuario_id  : int | None
        acao        : str          (ex: "login", "logout", "favoritar", "comentar", "403")
        detalhe     : str | None   (informação adicional opcional)
        ip          : str | None   (IP de origem — bônus)

    Requer header X-Internal-Token.
    """
    err = require_internal_token()
    if err:
        return err

    payload = request.get_json(silent=True) or {}
    usuario_id = payload.get('usuario_id')
    acao = str(payload.get('acao', '')).strip()
    detalhe = str(payload.get('detalhe', '')).strip()
    ip = str(payload.get('ip', '')).strip()

    if not acao:
        return json_error('Campo "acao" é obrigatório.')

    try:
        r = get_redis()
        entry = {
            'usuario_id': str(usuario_id) if usuario_id is not None else '',
            'acao': acao,
            'detalhe': detalhe,
            'ip': ip,
            # timestamp em milissegundos (para referência humana além do ID do stream)
            'ts_ms': str(int(time.time() * 1000)),
        }
        # XADD com trim automático para não crescer indefinidamente
        event_id = r.xadd(LOG_STREAM_KEY, entry, maxlen=MAX_LOG_ENTRIES, approximate=True)
        return jsonify({'ok': True, 'event_id': event_id}), 201
    except Exception as exc:
        app.logger.error('Erro ao gravar log no Redis: %s', exc)
        return json_error(f'Erro interno ao gravar log: {exc}', 500)


# ---------------------------------------------------------------------------
# Consultar eventos (uso interno — só admin pode chamar via catálogo)
# ---------------------------------------------------------------------------

@app.get('/logs')
def list_logs():
    """Retorna os últimos N eventos do stream de auditoria.

    Query params:
        n   : int (padrão 50, máx 500) — quantos eventos retornar
        start : str (padrão '-') — ID de início do range (XRANGE notation)
        end   : str (padrão '+') — ID de fim do range

    Requer header X-Internal-Token.
    """
    err = require_internal_token()
    if err:
        return err

    try:
        n = int(request.args.get('n', 50))
        n = max(1, min(n, 500))
    except (TypeError, ValueError):
        n = 50

    start = request.args.get('start', '-')
    end = request.args.get('end', '+')

    try:
        r = get_redis()
        stream_total = r.xlen(LOG_STREAM_KEY)

        acao_filter = request.args.get('acao', '').strip().lower()
        usuario_id_filter = request.args.get('usuario_id', '').strip()
        data_inicio = request.args.get('data_inicio')
        data_fim = request.args.get('data_fim')
        cursor = request.args.get('cursor', '').strip()

        # Se houver cursor para paginação contínua para trás
        effective_end = cursor if cursor else end

        # Se houver filtros, buscamos um número maior para garantir que encontramos os registros
        fetch_limit = min(MAX_LOG_ENTRIES, max(n * 4, 200)) if (acao_filter or usuario_id_filter or data_inicio or data_fim) else n + 1

        raw_entries = r.xrevrange(LOG_STREAM_KEY, max=effective_end, min=start, count=fetch_limit)
        
        # Se usamos cursor que já foi visto, pulamos o primeiro item se for idêntico
        if cursor and raw_entries and raw_entries[0][0] == cursor:
            raw_entries = raw_entries[1:]

        logs = []
        next_cursor = None

        for event_id, fields in raw_entries:
            # Filtro por ação
            if acao_filter and acao_filter not in (fields.get('acao', '')).lower():
                continue

            # Filtro por usuário
            if usuario_id_filter and fields.get('usuario_id') != usuario_id_filter:
                continue

            # Filtro por timestamp
            ts_ms = int(fields.get('ts_ms', 0))
            if data_inicio:
                try:
                    if ts_ms < int(data_inicio):
                        continue
                except ValueError:
                    pass
            if data_fim:
                try:
                    if ts_ms > int(data_fim):
                        continue
                except ValueError:
                    pass

            logs.append({
                'event_id': event_id,
                'usuario_id': fields.get('usuario_id') or None,
                'acao': fields.get('acao', ''),
                'detalhe': fields.get('detalhe', '') or None,
                'ip': fields.get('ip', '') or None,
                'ts_ms': ts_ms,
            })

            if len(logs) == n:
                next_cursor = event_id
                break

        if not next_cursor and len(raw_entries) > len(logs) and raw_entries:
            next_cursor = raw_entries[-1][0]

        return jsonify({
            'logs': logs,
            'count': len(logs),
            'stream_total': stream_total,
            'next_cursor': next_cursor,
        })
    except Exception as exc:
        app.logger.error('Erro ao consultar logs no Redis: %s', exc)
        return json_error(f'Erro interno ao consultar logs: {exc}', 500)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    port = int(os.getenv('LOG_PORT', '4000'))
    app.run(host='0.0.0.0', port=port, debug=os.getenv('LOG_DEBUG', '0') == '1')
