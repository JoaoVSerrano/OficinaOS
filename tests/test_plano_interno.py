"""T11.5: o plano da oficina é lido do banco a cada requisição, sem tocar na Stripe."""
from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import requests
from sqlalchemy.orm import Session


def _h():
    return {'X-Internal-Token': os.environ['INTERNAL_TOKEN']}


# --- payment-service ---------------------------------------------------------

def test_endpoint_interno_exige_token(pay_client):
    assert pay_client.get('/internal/plano?oficina_id=1').status_code == 403


def test_endpoint_exige_oficina_id(pay_client):
    assert pay_client.get('/internal/plano', headers=_h()).status_code == 400


def test_oficina_sem_linha_e_free(pay_client):
    r = pay_client.get('/internal/plano?oficina_id=77', headers=_h())
    assert r.status_code == 200
    assert r.get_json() == {'oficina_id': 77, 'plano': 'free', 'status': 'free', 'inadimplente': False,
                            'periodo_fim': None, 'valor_mensal_centavos': 0}


def test_pro_ativo_e_inadimplencia_vem_do_banco(pay_client, pay_engine):
    from payment_service.models import Assinatura
    with Session(pay_engine) as s:
        s.add(Assinatura(oficina_id=5, plano='pro', status='past_due', inadimplente=True,
                         valor_mensal_centavos=4900, stripe_customer_id='cus_5'))
        s.commit()
    corpo = pay_client.get('/internal/plano?oficina_id=5', headers=_h()).get_json()
    assert (corpo['plano'], corpo['status'], corpo['inadimplente']) == ('pro', 'past_due', True)
    assert corpo['valor_mensal_centavos'] == 4900


def test_decisao_do_plano_nao_chama_a_stripe_nem_o_redis(pay_client, pay_engine):
    with (patch('stripe.Subscription.list') as sub, patch('stripe.Customer.retrieve') as cus,
          patch('payment_service.app.get_redis') as redis):
        pay_client.get('/internal/plano?oficina_id=5', headers=_h())
    sub.assert_not_called()
    cus.assert_not_called()
    redis.assert_not_called()


def test_mudanca_no_banco_vale_na_requisicao_seguinte(pay_client, pay_engine):
    from payment_service.models import Assinatura
    assert pay_client.get('/internal/plano?oficina_id=5', headers=_h()).get_json()['plano'] == 'free'
    with Session(pay_engine) as s:
        s.add(Assinatura(oficina_id=5, plano='pro', status='active'))
        s.commit()
    assert pay_client.get('/internal/plano?oficina_id=5', headers=_h()).get_json()['plano'] == 'pro'


# --- gateway -----------------------------------------------------------------

def _resposta(plano):
    return SimpleNamespace(status_code=200, json=lambda: {'plano': plano})


def test_gateway_consulta_o_payment_a_cada_chamada(monkeypatch):
    from backend import app as core, planos
    chamadas = []
    estado = {'plano': 'free'}

    def fake(method, path, **kw):
        chamadas.append(path)
        return _resposta(estado['plano'])

    monkeypatch.setattr(core, '_forward_to_payment', fake)
    assert planos.plano_da_oficina(3) == 'free'
    estado['plano'] = 'pro'
    assert planos.plano_da_oficina(3) == 'pro'
    assert chamadas == ['/internal/plano?oficina_id=3'] * 2


@pytest.mark.parametrize('falha', [requests.ConnectionError('fora'), RuntimeError('x')])
def test_payment_fora_do_ar_cai_para_free(monkeypatch, falha):
    from backend import app as core, planos

    def fake(*a, **k):
        raise falha

    monkeypatch.setattr(core, '_forward_to_payment', fake)
    assert planos.plano_da_oficina(3) == 'free'


def test_resposta_de_erro_ou_plano_desconhecido_cai_para_free(monkeypatch):
    from backend import app as core, planos
    monkeypatch.setattr(core, '_forward_to_payment',
                        lambda *a, **k: SimpleNamespace(status_code=500, json=lambda: {'plano': 'pro'}))
    assert planos.plano_da_oficina(3) == 'free'
    monkeypatch.setattr(core, '_forward_to_payment', lambda *a, **k: _resposta('enterprise'))
    assert planos.plano_da_oficina(3) == 'free'


def test_21a_os_passa_no_pro_lido_do_payment(gw, monkeypatch):
    """Ponta a ponta no gateway: o Pro vindo do payment-service libera além do limite do Free."""
    from backend import app as core
    from backend.models import Oficina
    with gw.scope() as db:
        o = Oficina(nome='O', codigo_convite='PLANO-1')
        db.add(o)
        db.flush()
        of = o.id
    gw.auth.add('dono', of)
    monkeypatch.setattr(core, '_forward_to_payment', lambda *a, **k: _resposta('pro'))
    from backend import planos
    assert planos.limite(planos.plano_da_oficina(of), 'max_os_mes') is None
