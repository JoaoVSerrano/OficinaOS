"""T11.2: webhooks de assinatura (4 eventos), idempotentes e na mesma transação."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

SECRET = 'whsec_teste_unitario'


@pytest.fixture
def engine():
    from payment_service.database import Base
    import payment_service.models  # noqa: F401
    eng = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def client(engine):
    @contextmanager
    def scope():
        s = Session(engine, expire_on_commit=False)
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    with (
        patch('payment_service.database._check_required_env'),
        patch('payment_service.app.session_scope', scope),
        patch('payment_service.app.upgrade_database'),
        patch('payment_service.app.log_event'),
        patch.dict('os.environ', {'STRIPE_WEBHOOK_SECRET': SECRET}),
    ):
        from payment_service.app import app
        app.config['TESTING'] = True
        with app.test_client() as c:
            yield c


def _post(client, tipo, obj, event_id='evt_1', created=1000, secret=SECRET):
    payload = json.dumps({'id': event_id, 'object': 'event', 'type': tipo, 'created': created,
                          'data': {'object': obj}})
    t = int(time.time())
    sig = hmac.new(secret.encode(), f'{t}.{payload}'.encode(), hashlib.sha256).hexdigest()
    return client.post('/webhook', data=payload, content_type='application/json',
                       headers={'Stripe-Signature': f't={t},v1={sig}'})


def _assinatura(engine, oficina_id=10):
    from payment_service.models import Assinatura
    with Session(engine) as s:
        return s.scalar(select(Assinatura).where(Assinatura.oficina_id == oficina_id))


CHECKOUT = {'id': 'cs_1', 'customer': 'cus_1', 'subscription': 'sub_1', 'client_reference_id': '10',
            'metadata': {'oficina_id': '10', 'usuario_id': '4'}}


def test_assinatura_invalida_retorna_400_e_nao_grava(client, engine):
    r = _post(client, 'checkout.session.completed', CHECKOUT, secret='whsec_outro')
    assert r.status_code == 400
    assert _assinatura(engine) is None


def test_checkout_completo_muda_para_pro_e_guarda_customer_e_subscription(client, engine):
    assert _post(client, 'checkout.session.completed', CHECKOUT).status_code == 200
    a = _assinatura(engine)
    assert (a.plano, a.status, a.stripe_customer_id, a.stripe_subscription_id, a.usuario_id) == \
        ('pro', 'active', 'cus_1', 'sub_1', 4)
    assert a.valor_mensal_centavos == 4900


def test_evento_repetido_nao_duplica_efeito(client, engine):
    from payment_service.models import ProcessedWebhookEvent
    _post(client, 'checkout.session.completed', CHECKOUT)
    r = _post(client, 'checkout.session.completed', CHECKOUT)
    assert r.status_code == 200 and r.get_json().get('duplicate') is True
    with Session(engine) as s:
        assert len(s.scalars(select(ProcessedWebhookEvent)).all()) == 1


def test_deleted_volta_ao_free(client, engine):
    _post(client, 'checkout.session.completed', CHECKOUT, 'evt_1', 1000)
    _post(client, 'customer.subscription.deleted', {'id': 'sub_1', 'customer': 'cus_1', 'status': 'canceled'},
          'evt_2', 2000)
    a = _assinatura(engine)
    assert (a.plano, a.status, a.valor_mensal_centavos, a.inadimplente) == ('free', 'canceled', 0, False)


def test_updated_atualiza_status_e_periodo(client, engine):
    _post(client, 'checkout.session.completed', CHECKOUT, 'evt_1', 1000)
    _post(client, 'customer.subscription.updated',
          {'id': 'sub_1', 'customer': 'cus_1', 'status': 'past_due', 'current_period_end': 1893456000},
          'evt_2', 2000)
    a = _assinatura(engine)
    assert a.status == 'past_due' and a.periodo_fim is not None and a.plano == 'pro'


def test_updated_para_status_encerrado_rebaixa_para_free(client, engine):
    _post(client, 'checkout.session.completed', CHECKOUT, 'evt_1', 1000)
    _post(client, 'customer.subscription.updated', {'id': 'sub_1', 'customer': 'cus_1', 'status': 'unpaid'},
          'evt_2', 2000)
    assert _assinatura(engine).plano == 'free'


def test_payment_failed_marca_inadimplencia_e_pagamento_posterior_limpa(client, engine):
    _post(client, 'checkout.session.completed', CHECKOUT, 'evt_1', 1000)
    _post(client, 'invoice.payment_failed', {'customer': 'cus_1', 'subscription': 'sub_1'}, 'evt_2', 2000)
    assert _assinatura(engine).inadimplente is True
    _post(client, 'customer.subscription.updated', {'id': 'sub_1', 'customer': 'cus_1', 'status': 'active'},
          'evt_3', 3000)
    assert _assinatura(engine).inadimplente is False


def test_evento_fora_de_ordem_nao_desfaz_o_mais_novo(client, engine):
    _post(client, 'checkout.session.completed', CHECKOUT, 'evt_1', 1000)
    _post(client, 'customer.subscription.deleted', {'id': 'sub_1', 'customer': 'cus_1', 'status': 'canceled'},
          'evt_3', 3000)
    # updated mais antigo chega depois do deleted: não ressuscita o Pro
    r = _post(client, 'customer.subscription.updated', {'id': 'sub_1', 'customer': 'cus_1', 'status': 'active'},
              'evt_2', 2000)
    assert r.status_code == 200
    assert _assinatura(engine).plano == 'free'


def test_checkout_atrasado_nao_ressuscita_assinatura_cancelada(client, engine):
    _post(client, 'customer.subscription.deleted', {'id': 'sub_1', 'customer': 'cus_1', 'status': 'canceled'},
          'evt_3', 3000)
    assert _assinatura(engine) is None  # deleted sem linha: ignorado
    _post(client, 'checkout.session.completed', CHECKOUT, 'evt_1', 1000)
    assert _assinatura(engine).plano == 'pro'  # sem registro mais novo, vale


def test_evento_de_tipo_desconhecido_e_aceito(client):
    assert _post(client, 'charge.refunded', {'id': 'ch_1'}).status_code == 200


def test_efeito_que_falha_retorna_500_e_evento_nao_fica_marcado(client, engine):
    from payment_service.models import ProcessedWebhookEvent
    with patch('payment_service.webhooks._aplicar', side_effect=RuntimeError('boom')):
        r = _post(client, 'checkout.session.completed', CHECKOUT)
    assert r.status_code == 500
    with Session(engine) as s:
        assert s.scalars(select(ProcessedWebhookEvent)).all() == []
    # a Stripe reenvia o mesmo evento e agora funciona
    assert _post(client, 'checkout.session.completed', CHECKOUT).status_code == 200
    assert _assinatura(engine).plano == 'pro'


def test_checkout_sem_oficina_e_ignorado_sem_erro(client, engine):
    r = _post(client, 'checkout.session.completed', {'id': 'cs_x', 'customer': 'c', 'metadata': {}})
    assert r.status_code == 200
    assert _assinatura(engine) is None
