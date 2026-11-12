"""T11.6: o plano vem do banco; o entitlement legado (google_id + Stripe + cache Redis) não existe mais."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_payment_nao_tem_mais_rota_de_entitlement(pay_client):
    h = {'X-Internal-Token': os.environ['INTERNAL_TOKEN']}
    assert pay_client.get('/entitlement?google_id=g1', headers=h).status_code == 404


def test_gateway_nao_tem_mais_status_premium(gw):
    dono = gw.auth.add('dono', None)
    assert gw.client.get('/api/premium/status', **gw.como(dono)).status_code == 404


def test_codigo_de_decisao_de_plano_nao_usa_google_id_nem_cache_de_entitlement():
    app_py = (ROOT / 'payment_service' / 'app.py').read_text()
    for proibido in ('google_id', 'entitlement', 'ENTITLEMENT_CACHE_TTL', 'Subscription.list'):
        assert proibido not in app_py, proibido
    assert 'google_id' not in (ROOT / 'payment_service' / 'planos.py').read_text()
    assert 'entitlement' not in (ROOT / 'backend' / 'app.py').read_text().lower()


def test_google_id_so_resta_na_migracao_do_legado():
    achados = sorted(p.name for p in (ROOT / 'payment_service').glob('*.py') if 'google_id' in p.read_text())
    assert achados == ['migracao_legado.py', 'models.py']


def test_variavel_de_cache_de_entitlement_saiu_da_configuracao():
    for arq in ('.env.example', 'docker-compose.yml'):
        assert 'ENTITLEMENT_CACHE_TTL' not in (ROOT / arq).read_text(), arq
