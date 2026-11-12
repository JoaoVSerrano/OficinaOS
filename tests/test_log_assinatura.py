"""Eventos de assinatura no log levam oficina, papel e recurso (aparecem no painel e na auditoria)."""
from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import patch

from tests.test_webhooks_assinatura import CHECKOUT, _post


def _eventos(pay_client, tipo, obj, eid='evt_1', criado=1000):
    with patch('payment_service.app.log_event') as log:
        r = _post(pay_client, tipo, obj, eid, criado)
    assert r.status_code == 200
    return log


def test_assinatura_ativada_registra_a_oficina(pay_client):
    log = _eventos(pay_client, 'checkout.session.completed', CHECKOUT)
    assert log.call_args.args[0] == 'assinatura.ativada'
    assert log.call_args.kwargs['oficina_id'] == 10


def test_falha_de_pagamento_e_cancelamento_registram_a_oficina(pay_client):
    _post(pay_client, 'checkout.session.completed', CHECKOUT, 'evt_1', 1000)
    falha = _eventos(pay_client, 'invoice.payment_failed', {'customer': 'cus_1', 'subscription': 'sub_1'}, 'evt_2', 2000)
    assert (falha.call_args.args[0], falha.call_args.kwargs['oficina_id']) == ('assinatura.pagamento_falhou', 10)
    canc = _eventos(pay_client, 'customer.subscription.deleted',
                    {'id': 'sub_1', 'customer': 'cus_1', 'status': 'canceled'}, 'evt_3', 3000)
    assert (canc.call_args.args[0], canc.call_args.kwargs['oficina_id']) == ('assinatura.cancelada', 10)


def test_evento_sem_oficina_nao_inventa_oficina(pay_client):
    log = _eventos(pay_client, 'charge.refunded', {'id': 'ch_1'})
    assert log.call_args.args[0] == 'webhook_processado'
    assert log.call_args.kwargs.get('oficina_id') is None


def test_log_event_envia_oficina_papel_e_recurso_ao_log_service():
    from payment_service import app as pay
    with patch.object(pay._requests, 'post') as post:
        pay.log_event('assinatura.ativada', 'x=1', oficina_id=10)
    corpo = post.call_args.kwargs['json']
    assert corpo['acao'] == 'assinatura.ativada'            # eventos de negócio não levam prefixo
    assert corpo['oficina_id'] == 10 and corpo['papel'] == 'sistema'
    assert corpo['recurso'] == 'assinatura' and corpo['recurso_id'] == 10


def test_eventos_tecnicos_mantem_o_prefixo_payment():
    from payment_service import app as pay
    with patch.object(pay._requests, 'post') as post:
        pay.log_event('webhook_processado', 'x=1')
    corpo = post.call_args.kwargs['json']
    assert corpo['acao'] == 'payment:webhook_processado' and corpo.get('oficina_id') is None


def test_checkout_e_portal_registram_a_oficina(pay_client, pay_engine):
    from payment_service.models import Assinatura
    from sqlalchemy.orm import Session
    h = {'X-Internal-Token': os.environ['INTERNAL_TOKEN']}
    with Session(pay_engine) as s:
        s.add(Assinatura(oficina_id=10, stripe_customer_id='cus_1'))
        s.commit()
    with (patch.dict('os.environ', {'STRIPE_SECRET_KEY': 'sk_test_fake', 'STRIPE_PRICE_ID': 'price_t'}),
          patch('stripe.checkout.Session.create', return_value=SimpleNamespace(id='cs_1', url='https://x')),
          patch('stripe.billing_portal.Session.create', return_value=SimpleNamespace(url='https://p')),
          patch('payment_service.app.log_event') as log):
        pay_client.post('/checkout', json={'oficina_id': 10, 'usuario_id': 4}, headers=h)
        pay_client.post('/portal', json={'oficina_id': 10}, headers=h)
    assert [(c.args[0], c.kwargs['oficina_id']) for c in log.call_args_list] == [
        ('checkout_iniciado', 10), ('portal_aberto', 10)]
