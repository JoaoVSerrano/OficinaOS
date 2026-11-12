from __future__ import annotations
import hashlib
import hmac
import json
import os
import time
from typing import Any

import redis
import requests as _requests
import stripe
from flask import Flask, Response, jsonify, request
from prometheus_flask_exporter import PrometheusMetrics
from sqlalchemy import select

from payment_service.database import session_scope, upgrade_database
from payment_service.models import Assinatura, StripeCustomer
from payment_service.planos import plano_da_oficina
from payment_service.webhooks import processar_evento

app = Flask(__name__)
metrics = PrometheusMetrics(app)

INTERNAL_TOKEN = os.getenv('INTERNAL_TOKEN', '')
PAYMENT_PORT = int(os.getenv('PAYMENT_PORT', '5000'))

stripe.api_key = os.getenv('STRIPE_SECRET_KEY', '')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '')
STRIPE_PRICE_ID = os.getenv('STRIPE_PRICE_ID', '')
STRIPE_SUCCESS_URL = os.getenv('STRIPE_SUCCESS_URL', 'http://localhost:8080/?payment=success')
STRIPE_CANCEL_URL = os.getenv('STRIPE_CANCEL_URL', 'http://localhost:8080/?payment=cancel')

LOG_SERVICE_URL = os.getenv('LOG_SERVICE_URL', 'http://log-service:4000')
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379/0')
CACHE_TTL = int(os.getenv('ENTITLEMENT_CACHE_TTL', '300'))  # 5 minutos

START_TIME = time.time()
_redis_pool: redis.ConnectionPool | None = None

def json_error(message: str, status: int = 400):
    return jsonify({'error': message}), status

def require_internal_token():
    token = request.headers.get('X-Internal-Token', '')
    if not INTERNAL_TOKEN or token != INTERNAL_TOKEN:
        return json_error('Acesso não autorizado.', 403)
    return None

def get_redis():
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = redis.ConnectionPool.from_url(
            REDIS_URL,
            decode_responses=True,
            max_connections=20,
        )
    return redis.Redis(connection_pool=_redis_pool)

def log_event(acao: str, google_id: str | None = None, detalhe: str = '') -> None:
    try:
        _requests.post(
            f'{LOG_SERVICE_URL}/log',
            json={'usuario_id': None, 'acao': f'payment:{acao}', 'detalhe': detalhe, 'ip': ''},
            headers={'X-Internal-Token': INTERNAL_TOKEN},
            timeout=3,
        )
    except Exception as exc:
        app.logger.warning('log-service indisponível (acao=%s): %s', acao, exc)

import threading
_init_lock = threading.Lock()
_schema_ready = False

@app.before_request
def initialize():
    global _schema_ready
    if request.path == '/health' or request.method == 'OPTIONS':
        return None
    if _schema_ready:
        return None
    with _init_lock:
        if _schema_ready:
            return None
        try:
            upgrade_database()
            _schema_ready = True
        except Exception:
            app.logger.exception('Falha ao inicializar schema do payment-service.')
    return None

@app.get('/health')
def health():
    from datetime import datetime, timezone
    t0 = time.monotonic()
    db_ok = False
    db_err = None
    redis_ok = False
    redis_err = None
    stripe_ok = bool(stripe.api_key)

    try:
        with session_scope() as db:
            db.execute(select(1))
        db_ok = True
    except Exception as exc:
        db_err = str(exc)
        app.logger.error('BD indisponível em health: %s', exc)

    try:
        r = get_redis()
        r.ping()
        redis_ok = True
    except Exception as exc:
        redis_err = str(exc)
        app.logger.warning('Redis indisponível em health: %s', exc)
    
    latency_ms = round((time.monotonic() - t0) * 1000, 2)
    healthy = db_ok
    status_code = 200 if healthy else 503

    payload = {
        'status': 'healthy' if healthy else 'unhealthy',
        'service': 'payment-service',
        'version': '1.0.0',
        'uptime_seconds': round(time.time() - START_TIME, 1),
        'latency_ms': latency_ms,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'dependencies': {
            'database': {
                'status': 'connected' if db_ok else 'disconnected',
                'error': db_err,
            },
            'redis': {
                'status': 'connected' if redis_ok else 'disconnected',
                'error': redis_err,
            },
            'stripe': {
                'status': 'configured' if stripe_ok else 'not_configured',
                'price_id_configured': bool(STRIPE_PRICE_ID),
            },
        }
    }
    return jsonify(payload), status_code

def _get_stripe_customer_id(google_id: str) -> str | None:
    with session_scope() as db:
        record = db.scalar(select(StripeCustomer).where(StripeCustomer.google_id == google_id))
        return record.stripe_customer_id if record else None

def _check_entitlement_from_stripe(stripe_customer_id: str) -> dict[str, Any]:
    try:
        subscriptions = stripe.Subscription.list(
            customer=stripe_customer_id,
            status='all',
            limit=1,
        )
        if not subscriptions.data:
            return {'has_premium': False, 'status': 'no_subscription', 'plan': None, 'period_end': None}
        
        sub = subscriptions.data[0]
        active = sub.status in ('active', 'trialing')
        plan_name = None
        if sub.items.data:
            price = sub.items.data[0].price
            plan_name = price.get('nickname') or price.id
        
        period_end = None
        if sub.current_period_end:
            import datetime
            period_end = datetime.datetime.fromtimestamp(
                sub.current_period_end, tz=datetime.timezone.utc
            ).isoformat()
        
        return {
            'has_premium': active,
            'status': sub.status,
            'plan': plan_name,
            'period_end': period_end,
        }
    except stripe.StripeError as exc:
        app.logger.error('Erro Stripe ao verificar entitlement: %s', exc)
        return {'has_premium': False, 'status': 'stripe_error', 'plan': None, 'period_end': None}

@app.get('/entitlement')
def entitlement():
    err = require_internal_token()
    if err:
        return err
    
    google_id = request.args.get('google_id', '').strip()
    if not google_id:
        return json_error('Parâmetro google_id obrigatório.')
    
    if not stripe.api_key:
        return jsonify({'has_premium': False, 'status': 'stripe_not_configured', 'plan': None, 'period_end': None})
    
    cache_key = f'entitlement:{google_id}'
    try:
        r = get_redis()
        cached = r.get(cache_key)
        if cached:
            return jsonify(json.loads(cached))
    except Exception as exc:
        app.logger.warning('Falha no cache Redis (continuando sem cache): %s', exc)
    
    customer_id = _get_stripe_customer_id(google_id)
    if not customer_id:
        result = {'has_premium': False, 'status': 'no_customer', 'plan': None, 'period_end': None}
        return jsonify(result)
    
    result = _check_entitlement_from_stripe(customer_id)
    
    try:
        r = get_redis()
        r.setex(cache_key, CACHE_TTL, json.dumps(result))
    except Exception as exc:
        app.logger.warning('Falha ao gravar cache Redis: %s', exc)
    
    return jsonify(result)

@app.post('/checkout')
def create_checkout():
    """Checkout de assinatura Pro da oficina. O customer fica em `assinaturas`, ligado à oficina."""
    err = require_internal_token()
    if err:
        return err

    stripe_secret = os.getenv('STRIPE_SECRET_KEY') or stripe.api_key
    if not stripe_secret:
        return json_error('Pagamentos não configurados neste servidor.', 503)
    stripe.api_key = stripe_secret

    price_id = os.getenv('STRIPE_PRICE_ID', '')
    if not price_id:
        return json_error('Plano de assinatura não configurado.', 503)

    payload = request.get_json(silent=True) or {}
    try:
        oficina_id = int(payload.get('oficina_id'))
    except (TypeError, ValueError):
        return json_error('oficina_id obrigatório.')
    usuario_id = payload.get('usuario_id')
    usuario_id = int(usuario_id) if str(usuario_id or '').isdigit() else None
    email = str(payload.get('email', '')).strip()

    with session_scope() as db:
        a = db.scalar(select(Assinatura).where(Assinatura.oficina_id == oficina_id))
        if a and plano_da_oficina(db, oficina_id)['plano'] == 'pro':
            return json_error('Esta oficina já tem o plano Pro. Use "Gerenciar assinatura".', 409)
        customer_id = a.stripe_customer_id if a else None

    meta = {'oficina_id': str(oficina_id), 'usuario_id': str(usuario_id or '')}
    if not customer_id:
        try:
            customer = stripe.Customer.create(email=email or None, metadata={'oficina_id': str(oficina_id)})
            customer_id = customer.id
        except stripe.StripeError as exc:
            app.logger.error('Erro ao criar customer Stripe: %s', exc)
            return json_error('Falha ao iniciar assinatura.', 502)
        with session_scope() as db:
            a = db.scalar(select(Assinatura).where(Assinatura.oficina_id == oficina_id))
            if a is None:
                a = Assinatura(oficina_id=oficina_id)
                db.add(a)
            a.stripe_customer_id = customer_id
            a.usuario_id = usuario_id

    try:
        checkout_session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=['card'],
            line_items=[{'price': price_id, 'quantity': 1}],
            mode='subscription',
            success_url=STRIPE_SUCCESS_URL,
            cancel_url=STRIPE_CANCEL_URL,
            client_reference_id=str(oficina_id),
            metadata=meta,
            subscription_data={'metadata': meta},
        )
    except stripe.StripeError as exc:
        app.logger.error('Erro ao criar checkout session: %s', exc)
        return json_error('Falha ao criar sessão de pagamento.', 502)

    log_event('checkout_iniciado', detalhe=f'oficina_id={oficina_id} session_id={checkout_session.id}')
    return jsonify({'checkout_url': checkout_session.url}), 201

@app.post('/portal')
def create_portal():
    """Billing Portal da Stripe para o customer da oficina (cancelamento imediato é configurado no painel)."""
    err = require_internal_token()
    if err:
        return err

    stripe_secret = os.getenv('STRIPE_SECRET_KEY') or stripe.api_key
    if not stripe_secret:
        return json_error('Pagamentos não configurados neste servidor.', 503)
    stripe.api_key = stripe_secret

    payload = request.get_json(silent=True) or {}
    try:
        oficina_id = int(payload.get('oficina_id'))
    except (TypeError, ValueError):
        return json_error('oficina_id obrigatório.')

    with session_scope() as db:
        a = db.scalar(select(Assinatura).where(Assinatura.oficina_id == oficina_id))
        customer_id = a.stripe_customer_id if a else None
    if not customer_id:
        return json_error('Esta oficina ainda não tem assinatura. Assine o Pro em Plano e assinatura.', 409)

    frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:8080')
    try:
        portal_session = stripe.billing_portal.Session.create(customer=customer_id, return_url=frontend_url)
    except stripe.StripeError as exc:
        app.logger.error('Erro ao criar portal session: %s', exc)
        return json_error('Falha ao abrir portal de assinatura.', 502)

    log_event('portal_aberto', detalhe=f'oficina_id={oficina_id}')
    return jsonify({'portal_url': portal_session.url})

@app.post('/webhook')
def stripe_webhook():
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature', '')
    
    webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET', STRIPE_WEBHOOK_SECRET)
    if not webhook_secret:
        return json_error('Webhook secret não configurado.', 500)
    
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except (stripe.SignatureVerificationError, getattr(stripe, 'error', None) and getattr(stripe.error, 'SignatureVerificationError', Exception)):
        app.logger.warning('Assinatura de webhook Stripe inválida — requisição rejeitada.')
        return json_error('Assinatura inválida.', 400)
    except Exception as exc:
        if type(exc).__name__ == 'SignatureVerificationError':
            app.logger.warning('Assinatura de webhook Stripe inválida — requisição rejeitada.')
            return json_error('Assinatura inválida.', 400)
        app.logger.error('Erro ao construir evento webhook: %s', exc)
        return json_error('Payload inválido.', 400)
    
    event_id = event['id']
    event_type = event['type']

    try:
        with session_scope() as db:
            novo, negocio = processar_evento(db, event)
    except Exception:
        app.logger.exception('Falha ao processar webhook %s (%s).', event_id, event_type)
        return json_error('Falha ao processar o evento.', 500)

    if not novo:
        app.logger.info('Evento webhook %s já processado — ignorado.', event_id)
        return jsonify({'ok': True, 'duplicate': True})

    log_event(negocio or 'webhook_processado', detalhe=f'event_type={event_type} event_id={event_id}')
    return jsonify({'ok': True})

@app.get('/plan-details')
def get_plan_details():
    """Retorna detalhes do plano consultando a Stripe com cache Redis."""
    err = require_internal_token()
    if err:
        return err

    price_id = os.getenv('STRIPE_PRICE_ID', '')
    fallback = {
        'price_id': price_id,
        'name': 'Plano Premium',
        'currency': 'brl',
        'unit_amount': 990,
        'formatted_price': 'R$ 9,90',
        'interval': 'mês',
    }

    if not price_id or not stripe.api_key:
        return jsonify(fallback)

    cache_key = f'stripe:price:{price_id}'
    try:
        r = get_redis()
        cached = r.get(cache_key)
        if cached:
            return jsonify(json.loads(cached))
    except Exception:
        pass

    try:
        price = stripe.Price.retrieve(price_id)
        unit_amount = price.unit_amount or 990
        currency = (price.currency or 'brl').upper()
        amount_fmt = f"{currency} {unit_amount / 100:.2f}".replace('.', ',') if currency != 'BRL' else f"R$ {unit_amount / 100:.2f}".replace('.', ',')
        interval = (price.recurring.interval if price.recurring else 'mês')
        interval_label = 'mês' if interval == 'month' else 'ano' if interval == 'year' else interval

        data = {
            'price_id': price.id,
            'name': price.nickname or 'Plano Premium',
            'currency': price.currency or 'brl',
            'unit_amount': unit_amount,
            'formatted_price': amount_fmt,
            'interval': interval_label,
        }
        try:
            r = get_redis()
            r.setex(cache_key, 3600, json.dumps(data))
        except Exception:
            pass
        return jsonify(data)
    except Exception as exc:
        app.logger.warning('Erro ao buscar Price no Stripe: %s', exc)
        return jsonify(fallback)

@app.get('/api/docs/openapi.json')
def get_openapi_json():
    err = require_internal_token()
    if err:
        return err
    from payment_service.swagger_spec import get_openapi_json as _json_fn
    return Response(_json_fn(), content_type='application/json; charset=utf-8')

@app.get('/apidocs')
@app.get('/docs')
def apidocs():
    err = require_internal_token()
    if err:
        return err
    return """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>payment-service — Documentação OpenAPI</title>
  <link rel="stylesheet" type="text/css" href="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/5.11.0/swagger-ui.min.css" />
  <style>
    body { margin:0; background: #0f172a; color: #f8fafc; font-family: sans-serif; }
    .swagger-ui .topbar { background-color: #1e293b; border-bottom: 2px solid #e94560; }
  </style>
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/5.11.0/swagger-ui-bundle.min.js"></script>
  <script>
    window.onload = function() {
      SwaggerUIBundle({
        url: "/api/docs/openapi.json",
        dom_id: '#swagger-ui',
        deepLinking: true
      });
    };
  </script>
</body>
</html>""", 200, {'Content-Type': 'text/html; charset=utf-8'}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PAYMENT_PORT, debug=os.getenv('PAYMENT_DEBUG', '0') == '1')
