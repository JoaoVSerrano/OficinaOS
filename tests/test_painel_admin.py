"""T11.7: painel admin (planos, assinaturas ativas, MRR de teste e últimos eventos)."""
from __future__ import annotations

import os
from types import SimpleNamespace

from sqlalchemy.orm import Session


def _h():
    return {'X-Internal-Token': os.environ['INTERNAL_TOKEN']}


# --- payment-service: resumo interno ------------------------------------------

def test_resumo_exige_token_interno(pay_client):
    assert pay_client.get('/internal/resumo').status_code == 403


def test_resumo_vazio(pay_client):
    r = pay_client.get('/internal/resumo', headers=_h()).get_json()
    assert r == {'assinaturas_ativas': 0, 'mrr_centavos': 0, 'moeda': 'brl', 'inadimplentes': 0,
                 'oficinas_pro': []}


def test_mrr_e_a_soma_das_assinaturas_ativas(pay_client, pay_engine):
    from payment_service.models import Assinatura
    with Session(pay_engine) as s:
        s.add_all([
            Assinatura(oficina_id=1, plano='pro', status='active', valor_mensal_centavos=4900),
            Assinatura(oficina_id=2, plano='pro', status='trialing', valor_mensal_centavos=4900),
            Assinatura(oficina_id=3, plano='pro', status='active', valor_mensal_centavos=7000),
            # past_due continua Pro (acesso), mas não entra no MRR e conta como inadimplente
            Assinatura(oficina_id=4, plano='pro', status='past_due', valor_mensal_centavos=4900, inadimplente=True),
            # cancelada e Free não contam
            Assinatura(oficina_id=5, plano='free', status='canceled', valor_mensal_centavos=0),
            Assinatura(oficina_id=6, plano='free', status='free'),
        ])
        s.commit()
    r = pay_client.get('/internal/resumo', headers=_h()).get_json()
    assert r['assinaturas_ativas'] == 3
    assert r['mrr_centavos'] == 4900 + 4900 + 7000
    assert r['inadimplentes'] == 1
    assert r['oficinas_pro'] == [1, 2, 3, 4]


# --- gateway: painel ------------------------------------------------------------

def _oficinas(gw, n):
    from backend.models import Oficina
    ids = []
    with gw.scope() as db:
        for i in range(n):
            o = Oficina(nome=f'Oficina {i}', codigo_convite=f'PAINEL-{i}')
            db.add(o)
            db.flush()
            ids.append(o.id)
    return ids


def _simular(gw, monkeypatch, resumo, eventos=None):
    from backend import app as core, dominio

    def payment(method, path, **kw):
        assert path == '/internal/resumo'
        return SimpleNamespace(status_code=200, json=lambda: resumo)

    monkeypatch.setattr(core, '_forward_to_payment', payment)
    monkeypatch.setattr(dominio, '_eventos_recentes', lambda n: eventos or [])


def test_painel_so_para_admin(gw):
    of, = _oficinas(gw, 1)
    for papel in ('dono', 'mecanico', 'cliente'):
        uid = gw.auth.add(papel, of)
        assert gw.client.get('/api/admin/painel', **gw.como(uid)).status_code == 403
    assert gw.client.get('/api/admin/painel').status_code == 401


def test_painel_conta_oficinas_e_usuarios_por_plano_e_mrr(gw, monkeypatch):
    a, b, c = _oficinas(gw, 3)
    adm = gw.auth.add('admin', None)
    gw.auth.add('dono', a); gw.auth.add('mecanico', a); gw.auth.add('cliente', a)   # a: Pro, 3 usuários
    gw.auth.add('dono', b)                                                           # b: Free, 1
    gw.auth.add('dono', c); gw.auth.add('cliente', c)                                # c: Free, 2
    gw.auth.add('dono', None)                                                        # sem oficina
    _simular(gw, monkeypatch, {'assinaturas_ativas': 1, 'mrr_centavos': 4900, 'moeda': 'brl',
                               'inadimplentes': 0, 'oficinas_pro': [a, 999]},   # 999 não existe: ignorado
             eventos=[{'acao': 'assinatura.ativada', 'ts_ms': 1}])
    r = gw.client.get('/api/admin/painel', **gw.como(adm))
    assert r.status_code == 200
    p = r.get_json()
    assert p['oficinas_por_plano'] == {'free': 2, 'pro': 1}
    assert p['usuarios_por_plano'] == {'free': 3, 'pro': 3, 'sem_oficina': 1}
    assert p['assinaturas_ativas'] == 1
    assert p['mrr_centavos'] == 4900 and p['moeda'] == 'brl'
    assert p['eventos'] == [{'acao': 'assinatura.ativada', 'ts_ms': 1}]


def test_painel_sem_assinaturas_tudo_free(gw, monkeypatch):
    a, b = _oficinas(gw, 2)
    adm = gw.auth.add('admin', None)
    _simular(gw, monkeypatch, {'assinaturas_ativas': 0, 'mrr_centavos': 0, 'moeda': 'brl',
                               'inadimplentes': 0, 'oficinas_pro': []})
    p = gw.client.get('/api/admin/painel', **gw.como(adm)).get_json()
    assert p['oficinas_por_plano'] == {'free': 2, 'pro': 0} and p['mrr_centavos'] == 0


def test_painel_com_payment_fora_do_ar_avisa_em_vez_de_inventar(gw, monkeypatch):
    import requests
    from backend import app as core, dominio
    _oficinas(gw, 1)
    adm = gw.auth.add('admin', None)

    def cai(*a, **k):
        raise requests.ConnectionError('fora')

    monkeypatch.setattr(core, '_forward_to_payment', cai)
    monkeypatch.setattr(dominio, '_eventos_recentes', lambda n: [])
    assert gw.client.get('/api/admin/painel', **gw.como(adm)).status_code == 503
