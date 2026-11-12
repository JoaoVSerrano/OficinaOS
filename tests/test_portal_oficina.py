"""T11.4: portal do cliente Stripe (só o dono; oficina sem customer => 409)."""
from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy.orm import Session

ENV = {'STRIPE_SECRET_KEY': 'sk_test_fake'}


def _h():
    return {'X-Internal-Token': os.environ['INTERNAL_TOKEN']}


def test_oficina_sem_customer_recebe_409_com_mensagem(pay_client):
    with patch.dict('os.environ', ENV), patch('stripe.billing_portal.Session.create') as criar:
        r = pay_client.post('/portal', json={'oficina_id': 10}, headers=_h())
    assert r.status_code == 409
    assert 'Assine o Pro' in r.get_json()['error']
    criar.assert_not_called()


def test_portal_abre_para_o_customer_da_oficina(pay_client, pay_engine):
    from payment_service.models import Assinatura
    with Session(pay_engine) as s:
        s.add(Assinatura(oficina_id=10, stripe_customer_id='cus_10'))
        s.add(Assinatura(oficina_id=11, stripe_customer_id='cus_11'))
        s.commit()
    with patch.dict('os.environ', ENV), patch(
            'stripe.billing_portal.Session.create',
            return_value=SimpleNamespace(url='https://billing.stripe.test/p')) as criar:
        r = pay_client.post('/portal', json={'oficina_id': 10}, headers=_h())
    assert r.status_code == 200 and r.get_json()['portal_url'] == 'https://billing.stripe.test/p'
    assert criar.call_args.kwargs['customer'] == 'cus_10'


def test_portal_sem_oficina_id_retorna_400(pay_client):
    with patch.dict('os.environ', ENV):
        assert pay_client.post('/portal', json={}, headers=_h()).status_code == 400


def test_portal_sem_token_interno_403(pay_client):
    assert pay_client.post('/portal', json={'oficina_id': 10}).status_code == 403


# --- gateway -----------------------------------------------------------------

def _of(gw):
    from backend.models import Oficina
    with gw.scope() as db:
        o = Oficina(nome='Oficina', codigo_convite='PORTAL-1')
        db.add(o)
        db.flush()
        return o.id


def test_mecanico_e_cliente_nao_abrem_o_portal_403(gw):
    of = _of(gw)
    for papel in ('mecanico', 'cliente'):
        uid = gw.auth.add(papel, of)
        assert gw.client.post('/api/payment/portal', **gw.como(uid)).status_code == 403


def test_sem_login_401(gw):
    assert gw.client.post('/api/payment/portal').status_code == 401


def test_dono_abre_portal_com_a_oficina_da_sessao(gw, monkeypatch):
    from backend import app as core
    of = _of(gw)
    dono = gw.auth.add('dono', of)
    chamadas = []

    def fake(method, path, **kw):
        chamadas.append((method, path, kw.get('json')))
        return SimpleNamespace(status_code=200, json=lambda: {'portal_url': 'https://p'})

    monkeypatch.setattr(core, '_forward_to_payment', fake)
    r = gw.client.post('/api/payment/portal', json={'oficina_id': 999}, **gw.como(dono))
    assert r.status_code == 200
    assert chamadas == [('POST', '/portal', {'oficina_id': of})]
    assert any(e['acao'] == 'assinatura.portal_aberto' for e in gw.eventos)


def test_gateway_repassa_409_do_payment(gw, monkeypatch):
    from backend import app as core
    dono = gw.auth.add('dono', _of(gw))
    monkeypatch.setattr(core, '_forward_to_payment',
                        lambda *a, **k: SimpleNamespace(status_code=409, json=lambda: {'error': 'Assine o Pro'}))
    r = gw.client.post('/api/payment/portal', **gw.como(dono))
    assert r.status_code == 409
