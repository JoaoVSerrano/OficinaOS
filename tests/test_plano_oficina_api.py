"""T11.8 (API): GET /api/plano — plano atual, uso e limites da oficina para a tela "Plano e assinatura"."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from backend.models import Cliente, Oficina, OrdemServico, Veiculo

ROOT = Path(__file__).resolve().parent.parent


def _oficina(gw, codigo='PLANO-API'):
    with gw.scope() as db:
        o = Oficina(nome='Oficina', codigo_convite=codigo)
        db.add(o)
        db.flush()
        return o.id


def _os(gw, oficina_id, n):
    from backend.ordens import agora
    with gw.scope() as db:
        cli = Cliente(oficina_id=oficina_id, nome='C')
        db.add(cli)
        db.flush()
        v = Veiculo(oficina_id=oficina_id, cliente_id=cli.id, placa='ABC1D23', marca='VW', modelo='Gol')
        db.add(v)
        db.flush()
        for i in range(n):
            db.add(OrdemServico(oficina_id=oficina_id, veiculo_id=v.id, criada_por=1, status='aberta',
                                descricao=f'OS {i}', valor_total_centavos=0, criada_em=agora(), atualizada_em=agora()))


def _payment(monkeypatch, **dados):
    from backend import app as core
    corpo = {'plano': 'free', 'status': 'free', 'inadimplente': False, 'periodo_fim': None,
             'valor_mensal_centavos': 0, **dados}
    monkeypatch.setattr(core, '_forward_to_payment', lambda *a, **k: SimpleNamespace(status_code=200, json=lambda: corpo))


def test_dono_free_ve_plano_uso_e_limites(gw):
    of = _oficina(gw)
    dono = gw.auth.add('dono', of)
    gw.auth.add('mecanico', of)
    _os(gw, of, 3)
    r = gw.client.get('/api/plano', **gw.como(dono))
    assert r.status_code == 200
    p = r.get_json()
    assert p['plano'] == 'free' and p['nome'] == 'Free' and p['pode_gerenciar'] is True
    assert p['uso'] == {'os_mes': 3, 'mecanicos': 1}
    assert p['limites'] == {'max_os_mes': 20, 'max_mecanicos': 1, 'max_anexos_por_os': 3}
    assert p['preco_pro_centavos'] == 4900 and p['inadimplente'] is False


def test_pro_nao_tem_limites_e_mostra_valor_e_renovacao(gw, monkeypatch):
    of = _oficina(gw)
    dono = gw.auth.add('dono', of)
    _payment(monkeypatch, plano='pro', status='active', valor_mensal_centavos=4900, periodo_fim='2026-12-12T00:00:00')
    p = gw.client.get('/api/plano', **gw.como(dono)).get_json()
    assert p['plano'] == 'pro' and p['nome'] == 'Pro'
    assert p['limites'] == {'max_os_mes': None, 'max_mecanicos': None, 'max_anexos_por_os': None}
    assert p['valor_mensal_centavos'] == 4900 and p['periodo_fim'] == '2026-12-12T00:00:00'


def test_inadimplencia_chega_na_tela(gw, monkeypatch):
    of = _oficina(gw)
    dono = gw.auth.add('dono', of)
    _payment(monkeypatch, plano='pro', status='past_due', inadimplente=True)
    assert gw.client.get('/api/plano', **gw.como(dono)).get_json()['inadimplente'] is True


def test_mecanico_ve_mas_nao_gerencia(gw):
    of = _oficina(gw)
    mec = gw.auth.add('mecanico', of)
    p = gw.client.get('/api/plano', **gw.como(mec)).get_json()
    assert p['pode_gerenciar'] is False


def test_cliente_admin_e_anonimo_nao_veem_o_plano(gw):
    of = _oficina(gw)
    cli, adm = gw.auth.add('cliente', of), gw.auth.add('admin', None)
    assert gw.client.get('/api/plano', **gw.como(cli)).status_code == 403
    assert gw.client.get('/api/plano', **gw.como(adm)).status_code == 403
    assert gw.client.get('/api/plano').status_code == 401


def test_uso_e_so_da_propria_oficina(gw):
    a, b = _oficina(gw, 'A'), _oficina(gw, 'B')
    dono_a = gw.auth.add('dono', a)
    _os(gw, b, 5)
    assert gw.client.get('/api/plano', **gw.como(dono_a)).get_json()['uso']['os_mes'] == 0


def test_urls_de_retorno_do_checkout_levam_a_tela_do_plano():
    for arq in ('.env.example', 'docker-compose.yml', 'payment_service/app.py'):
        texto = (ROOT / arq).read_text()
        assert '/app/plano?assinatura=ok' in texto, arq
        assert '/app/plano?assinatura=cancelada' in texto, arq
