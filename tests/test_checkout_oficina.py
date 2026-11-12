"""T11.3: checkout de assinatura por oficina (só o dono) e customer reutilizado."""
from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.orm import Session

ENV = {'STRIPE_SECRET_KEY': 'sk_test_fake', 'STRIPE_PRICE_ID': 'price_pro_teste'}


def _headers():
    return {'X-Internal-Token': os.environ['INTERNAL_TOKEN']}


def _stripe_fakes():
    cliente = patch('stripe.Customer.create', return_value=SimpleNamespace(id='cus_novo'))
    sessao = patch('stripe.checkout.Session.create',
                   return_value=SimpleNamespace(id='cs_1', url='https://checkout.stripe.test/cs_1'))
    return cliente, sessao


def _assinatura(engine, oficina_id=10):
    from payment_service.models import Assinatura
    with Session(engine) as s:
        return s.scalar(select(Assinatura).where(Assinatura.oficina_id == oficina_id))


# --- payment-service ---------------------------------------------------------

def test_checkout_cria_customer_guarda_na_oficina_e_envia_referencias(pay_client, pay_engine):
    cliente, sessao = _stripe_fakes()
    with patch.dict('os.environ', ENV), cliente as c, sessao as s:
        r = pay_client.post('/checkout', json={'oficina_id': 10, 'usuario_id': 4, 'email': 'dono@oficinaos.example'},
                            headers=_headers())
    assert r.status_code == 201 and r.get_json()['checkout_url'].startswith('https://checkout.stripe.test/')
    assert c.call_args.kwargs['metadata']['oficina_id'] == '10'
    kw = s.call_args.kwargs
    assert kw['customer'] == 'cus_novo' and kw['mode'] == 'subscription'
    assert kw['client_reference_id'] == '10'
    assert kw['metadata'] == {'oficina_id': '10', 'usuario_id': '4'}
    assert kw['subscription_data']['metadata'] == {'oficina_id': '10', 'usuario_id': '4'}
    a = _assinatura(pay_engine)
    assert (a.stripe_customer_id, a.usuario_id, a.plano) == ('cus_novo', 4, 'free')


def test_checkout_reutiliza_customer_da_oficina(pay_client, pay_engine):
    from payment_service.models import Assinatura
    with Session(pay_engine) as s:
        s.add(Assinatura(oficina_id=10, stripe_customer_id='cus_existente'))
        s.commit()
    cliente, sessao = _stripe_fakes()
    with patch.dict('os.environ', ENV), cliente as c, sessao as s:
        r = pay_client.post('/checkout', json={'oficina_id': 10, 'usuario_id': 4}, headers=_headers())
    assert r.status_code == 201
    c.assert_not_called()
    assert s.call_args.kwargs['customer'] == 'cus_existente'


def test_oficina_ja_pro_recebe_409(pay_client, pay_engine):
    from payment_service.models import Assinatura
    with Session(pay_engine) as s:
        s.add(Assinatura(oficina_id=10, stripe_customer_id='cus_1', plano='pro', status='active'))
        s.commit()
    cliente, sessao = _stripe_fakes()
    with patch.dict('os.environ', ENV), cliente, sessao as s:
        r = pay_client.post('/checkout', json={'oficina_id': 10, 'usuario_id': 4}, headers=_headers())
    assert r.status_code == 409
    s.assert_not_called()


def test_checkout_sem_oficina_id_retorna_400(pay_client):
    with patch.dict('os.environ', ENV):
        r = pay_client.post('/checkout', json={'usuario_id': 4}, headers=_headers())
    assert r.status_code == 400


# --- gateway -----------------------------------------------------------------

def _of(gw, codigo='CHK-1'):
    from backend.models import Oficina
    with gw.scope() as db:
        o = Oficina(nome='Oficina', codigo_convite=codigo)
        db.add(o)
        db.flush()
        return o.id


def test_mecanico_e_cliente_nao_assinam_403(gw):
    of = _of(gw)
    mec, cli = gw.auth.add('mecanico', of), gw.auth.add('cliente', of)
    for uid in (mec, cli):
        assert gw.client.post('/api/payment/checkout', **gw.como(uid)).status_code == 403


def test_sem_login_401(gw):
    assert gw.client.post('/api/payment/checkout').status_code == 401


def test_dono_assina_com_oficina_do_proprio_usuario_e_nao_do_corpo(gw, monkeypatch):
    from backend import app as core
    of = _of(gw)
    dono = gw.auth.add('dono', of)
    chamadas = []

    def fake(method, path, **kw):
        chamadas.append((method, path, kw.get('json')))
        return SimpleNamespace(status_code=201, json=lambda: {'checkout_url': 'https://x'})

    monkeypatch.setattr(core, '_forward_to_payment', fake)
    r = gw.client.post('/api/payment/checkout', json={'oficina_id': 999}, **gw.como(dono))
    assert r.status_code == 201
    metodo, path, corpo = chamadas[0]
    assert (metodo, path) == ('POST', '/checkout')
    assert corpo['oficina_id'] == of and corpo['usuario_id'] == dono
