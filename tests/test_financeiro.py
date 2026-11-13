"""Histórico do veículo, pagamentos recebidos nas OS e resumo financeiro do mês (backend/financeiro.py)."""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from backend import ordens
from backend.models import Orcamento, OrdemServico, PagamentoOS
from tests.test_ordens import Cenario


@pytest.fixture
def c(gw):
    return Cenario(gw)


def _orcamento_aprovado(c, os_id, desconto, subtotal=10000):
    with c.gw.scope() as db:
        db.add(Orcamento(os_id=os_id, versao=1, status='aprovado', itens_json='[]', subtotal_centavos=subtotal,
                         desconto_centavos=desconto, total_centavos=subtotal - desconto,
                         validade_ate=date(2099, 1, 1), token_hash=f'{os_id:064d}', criado_por=c.dono))


def _pronta(c, valor=10000, veiculo=None, uid=None, **extra):
    """OS da oficina do `uid` (padrão: dono da A) com um item de `valor` e status `pronta`."""
    uid = uid or c.dono
    os_ = c.abrir(uid, veiculo, **extra)
    assert c.item(os_['id'], uid, valor).status_code == 201
    for destino in ('orcamento_aprovado', 'em_servico', 'pronta'):
        assert c.status(os_['id'], uid, destino).status_code == 200
    return os_['id']


def _pagar(c, os_id, valor, forma='pix', uid=None, **extra):
    return c.req('post', f'/api/os/{os_id}/pagamentos', uid or c.dono,
                 json={'valor_centavos': valor, 'forma': forma, **extra})


def _url_pag(os_id):
    return f'/api/os/{os_id}/pagamentos'


# --- histórico do veículo -------------------------------------------------------

def test_historico_ordenado_com_km_e_ultimo_km(c):
    a = c.abrir(km_entrada=40000)
    b = c.abrir(km_entrada=52000)
    d = c.abrir()  # sem km: não muda o último km
    r = c.req('get', f'/api/veiculos/{c.v_cli}/historico', c.dono)
    assert r.status_code == 200
    corpo = r.get_json()
    assert [o['id'] for o in corpo['ordens']] == [d['id'], b['id'], a['id']]
    assert [o['km_entrada'] for o in corpo['ordens']] == [None, 52000, 40000]
    assert corpo['ultimo_km'] == 52000
    assert corpo['veiculo'] == {'placa': 'MAR1N01', 'marca': 'M', 'modelo': 'X', 'ano': None}
    primeira = corpo['ordens'][0]
    for campo in ('id', 'status', 'descricao', 'km_entrada', 'criada_em', 'entregue_em', 'valor_total_centavos',
                  'valor_devido_centavos', 'pago_centavos'):
        assert campo in primeira


def test_historico_sem_os_e_ultimo_km_nulo(c):
    corpo = c.req('get', f'/api/veiculos/{c.v_out}/historico', c.dono).get_json()
    assert corpo['ordens'] == [] and corpo['ultimo_km'] is None


def test_historico_do_dono_traz_pago_e_devido(c):
    os_id = _pronta(c, 20000)
    _orcamento_aprovado(c, os_id, 5000)
    assert _pagar(c, os_id, 4000).status_code == 201
    o = c.req('get', f'/api/veiculos/{c.v_cli}/historico', c.dono).get_json()['ordens'][0]
    assert o['valor_devido_centavos'] == 15000 and o['pago_centavos'] == 4000


def test_cliente_ve_o_proprio_veiculo_sem_valores_de_pagamento(c):
    os_id = _pronta(c)
    _pagar(c, os_id, 1000)
    r = c.req('get', f'/api/veiculos/{c.v_cli}/historico', c.cli)
    assert r.status_code == 200
    corpo = r.get_json()
    assert len(corpo['ordens']) == 1
    texto = r.get_data(as_text=True)
    assert 'pago' not in texto and 'devido' not in texto and 'pagamento' not in texto


def test_cliente_nao_ve_veiculo_de_outro_cliente(c):
    c.abrir(veiculo=c.v_out)
    assert c.req('get', f'/api/veiculos/{c.v_out}/historico', c.cli).status_code == 404


def test_mecanico_so_ve_as_os_atribuidas_no_historico(c):
    minha = c.abrir(mecanico_id=c.mec1)
    c.abrir(mecanico_id=c.mec2)
    c.abrir()
    r = c.req('get', f'/api/veiculos/{c.v_cli}/historico', c.mec1)
    assert r.status_code == 200
    assert [o['id'] for o in r.get_json()['ordens']] == [minha['id']]


def test_historico_ignora_os_excluida(c):
    os_ = c.abrir(km_entrada=99000)
    c.req('delete', f'/api/os/{os_["id"]}', c.dono)
    corpo = c.req('get', f'/api/veiculos/{c.v_cli}/historico', c.dono).get_json()
    assert corpo['ordens'] == [] and corpo['ultimo_km'] is None


def test_historico_de_outra_oficina_404(c):
    assert c.req('get', f'/api/veiculos/{c.v_cli}/historico', c.dono_b).status_code == 404
    assert c.req('get', f'/api/veiculos/{c.v_b}/historico', c.dono).status_code == 404
    assert c.req('get', '/api/veiculos/99999/historico', c.dono).status_code == 404
    assert any(e['acao'] == 'acesso_negado' and e['usuario_id'] == c.dono_b for e in c.gw.eventos)


# --- pagamentos ------------------------------------------------------------------

def test_pagamento_em_os_aberta_409(c):
    os_ = c.abrir()
    c.item(os_['id'])
    assert _pagar(c, os_['id'], 1000).status_code == 409


@pytest.mark.parametrize('valor', [0, -100, True, 10.5, '1000', None])
def test_valor_invalido_400(c, valor):
    os_id = _pronta(c)
    assert _pagar(c, os_id, valor).status_code == 400


@pytest.mark.parametrize('forma', ['cheque', '', None, 7])
def test_forma_invalida_400(c, forma):
    os_id = _pronta(c)
    assert _pagar(c, os_id, 1000, forma=forma).status_code == 400


@pytest.mark.parametrize('pago_em', ['12/11/2026', '2026-13-01', '2026-02-30', 'ontem', 20261101])
def test_data_em_formato_invalido_400(c, pago_em):
    os_id = _pronta(c)
    assert _pagar(c, os_id, 1000, pago_em=pago_em).status_code == 400


def test_data_futura_400(c):
    os_id = _pronta(c)
    amanha = (ordens.agora().date() + timedelta(days=1)).isoformat()
    assert _pagar(c, os_id, 1000, pago_em=amanha).status_code == 400


def test_observacao_longa_400(c):
    os_id = _pronta(c)
    assert _pagar(c, os_id, 1000, observacao='x' * 256).status_code == 400


def test_pagamento_parcial_e_saldo(c):
    os_id = _pronta(c, 10000)
    r = _pagar(c, os_id, 3000, forma='dinheiro', observacao='Sinal')
    assert r.status_code == 201
    corpo = r.get_json()
    assert corpo['valor_devido_centavos'] == 10000 and corpo['pago_centavos'] == 3000
    assert corpo['saldo_centavos'] == 7000
    pag = corpo['pagamentos'][0]
    assert pag['forma'] == 'dinheiro' and pag['valor_centavos'] == 3000 and pag['observacao'] == 'Sinal'
    assert pag['pago_em'] == ordens.agora().date().isoformat() and pag['registrado_por'] == c.dono
    r = _pagar(c, os_id, 7000, pago_em='2026-01-15')
    assert r.status_code == 201 and r.get_json()['saldo_centavos'] == 0
    lista = c.req('get', _url_pag(os_id), c.dono).get_json()
    assert len(lista['pagamentos']) == 2 and lista['pago_centavos'] == 10000 and lista['saldo_centavos'] == 0


def test_pagamento_acima_do_saldo_409(c):
    os_id = _pronta(c, 10000)
    assert _pagar(c, os_id, 10001).status_code == 409
    assert _pagar(c, os_id, 6000).status_code == 201
    r = _pagar(c, os_id, 4001)
    assert r.status_code == 409 and 'saldo' in r.get_json()['error']


def test_excesso_considera_desconto_do_orcamento_aprovado(c):
    os_id = _pronta(c, 10000)
    _orcamento_aprovado(c, os_id, 2500)
    assert _pagar(c, os_id, 8000).status_code == 409
    r = _pagar(c, os_id, 7500)
    assert r.status_code == 201 and r.get_json()['valor_devido_centavos'] == 7500
    assert r.get_json()['saldo_centavos'] == 0


def test_pagamento_em_os_entregue_e_entrega_sem_pagamento(c):
    os_id = _pronta(c, 10000)
    assert c.status(os_id, c.dono, 'entregue').status_code == 200  # "fiado": entrega não exige pagamento
    assert _pagar(c, os_id, 10000, forma='boleto').status_code == 201


def test_remover_pagamento(c):
    os_id = _pronta(c, 10000)
    pag_id = _pagar(c, os_id, 4000).get_json()['pagamentos'][0]['id']
    r = c.req('delete', f'{_url_pag(os_id)}/{pag_id}', c.dono)
    assert r.status_code == 200
    lista = c.req('get', _url_pag(os_id), c.dono).get_json()
    assert lista['pagamentos'] == [] and lista['saldo_centavos'] == 10000
    assert c.req('delete', f'{_url_pag(os_id)}/{pag_id}', c.dono).status_code == 404


def test_remover_pagamento_de_outra_os_404(c):
    os1, os2 = _pronta(c), _pronta(c)
    pag_id = _pagar(c, os1, 1000).get_json()['pagamentos'][0]['id']
    assert c.req('delete', f'{_url_pag(os2)}/{pag_id}', c.dono).status_code == 404
    with c.gw.scope() as db:
        assert db.get(PagamentoOS, pag_id) is not None


def test_mecanico_e_cliente_403_nos_pagamentos(c):
    os_id = _pronta(c, mecanico_id=c.mec1)
    pag_id = _pagar(c, os_id, 1000).get_json()['pagamentos'][0]['id']
    for uid in (c.mec1, c.cli):
        assert c.req('get', _url_pag(os_id), uid).status_code == 403
        assert _pagar(c, os_id, 1000, uid=uid).status_code == 403
        assert c.req('delete', f'{_url_pag(os_id)}/{pag_id}', uid).status_code == 403


def test_pagamentos_de_outra_oficina_404(c):
    os_id = _pronta(c)
    pag_id = _pagar(c, os_id, 1000).get_json()['pagamentos'][0]['id']
    assert c.req('get', _url_pag(os_id), c.dono_b).status_code == 404
    assert _pagar(c, os_id, 1000, uid=c.dono_b).status_code == 404
    assert c.req('delete', f'{_url_pag(os_id)}/{pag_id}', c.dono_b).status_code == 404
    with c.gw.scope() as db:
        assert db.get(PagamentoOS, pag_id) is not None


def test_pagamentos_de_os_excluida_404(c):
    os_id = _pronta(c)
    c.req('delete', f'/api/os/{os_id}', c.dono)
    assert c.req('get', _url_pag(os_id), c.dono).status_code == 404
    assert _pagar(c, os_id, 1000).status_code == 404


def test_eventos_de_pagamento_com_oficina(c):
    os_id = _pronta(c)
    pag_id = _pagar(c, os_id, 2500, forma='pix').get_json()['pagamentos'][0]['id']
    c.req('delete', f'{_url_pag(os_id)}/{pag_id}', c.dono)
    reg = [e for e in c.gw.eventos if e['acao'] == 'pagamento.registrado']
    rem = [e for e in c.gw.eventos if e['acao'] == 'pagamento.removido']
    assert len(reg) == 1 and len(rem) == 1
    assert reg[0]['oficina_id'] == c.of_a and rem[0]['oficina_id'] == c.of_a
    assert reg[0]['detalhe']['valor_centavos'] == 2500 and reg[0]['detalhe']['forma'] == 'pix'


# --- resumo financeiro -------------------------------------------------------------

def _pagamento_direto(c, os_id, valor, forma, pago_em):
    with c.gw.scope() as db:
        db.add(PagamentoOS(os_id=os_id, valor_centavos=valor, forma=forma, pago_em=pago_em, registrado_por=c.dono))


def _entregue_em(c, os_id, quando):
    with c.gw.scope() as db:
        o = db.get(OrdemServico, os_id)
        o.status, o.entregue_em = 'entregue', quando


@pytest.fixture
def dados_mes(c):
    """Março/2026 com pagamento em 31/03 e outro em 01/04, desconto, fiado, OS excluída e outra oficina."""
    os1 = _pronta(c, 10000)                       # entregue em março, quitada (parte em abril)
    _entregue_em(c, os1, datetime(2026, 3, 15, 10, 0))
    assert _pagar(c, os1, 6000, forma='pix', pago_em='2026-03-31').status_code == 201
    assert _pagar(c, os1, 4000, forma='dinheiro', pago_em='2026-04-01').status_code == 201

    os2 = _pronta(c, 20000)                       # pronta, desconto 5000, paga 5000 em março -> falta 10000
    _orcamento_aprovado(c, os2, 5000, subtotal=20000)
    assert _pagar(c, os2, 3000, forma='dinheiro', pago_em='2026-03-10').status_code == 201
    assert _pagar(c, os2, 2000, forma='cartao_credito', pago_em='2026-03-01').status_code == 201

    os3 = _pronta(c, 30000)                       # excluída: não conta em nada
    _pagar(c, os3, 1000, forma='boleto', pago_em='2026-03-05')
    _entregue_em(c, os3, datetime(2026, 3, 20, 9, 0))
    c.req('delete', f'/api/os/{os3}', c.dono)

    os4 = _pronta(c, 7000)                        # entregue em 01/04 00:00: não é de março
    _entregue_em(c, os4, datetime(2026, 4, 1, 0, 0))

    aberta = c.abrir()                            # aberta: não entra no a receber
    c.item(aberta['id'], valor=9999)

    os_b = _pronta(c, 50000, veiculo=c.v_b, uid=c.dono_b)  # oficina B: nunca aparece no resumo da A
    assert _pagar(c, os_b, 1234, forma='pix', uid=c.dono_b, pago_em='2026-03-20').status_code == 201
    _entregue_em(c, os_b, datetime(2026, 3, 21, 9, 0))
    return {'os1': os1, 'os2': os2}


def _resumo(c, uid=None, mes=None):
    url = '/api/financeiro/resumo' + (f'?mes={mes}' if mes else '')
    return c.req('get', url, uid or c.dono)


def test_resumo_do_mes(c, dados_mes):
    r = _resumo(c, mes='2026-03')
    assert r.status_code == 200
    corpo = r.get_json()
    assert corpo['mes'] == '2026-03'
    assert corpo['faturado_centavos'] == 6000 + 3000 + 2000
    assert corpo['por_forma'] == {'pix': 6000, 'dinheiro': 3000, 'cartao_credito': 2000}
    assert corpo['os_entregues'] == 1
    assert corpo['ticket_medio_centavos'] == 11000 // 2
    # hoje: os1 quitada, os2 15000 - 5000, os4 fiado 7000; aberta, excluída e oficina B fora
    assert corpo['a_receber_centavos'] == 10000 + 7000


def test_resumo_do_mes_seguinte_pega_so_o_dia_primeiro(c, dados_mes):
    corpo = _resumo(c, mes='2026-04').get_json()
    assert corpo['faturado_centavos'] == 4000 and corpo['por_forma'] == {'dinheiro': 4000}
    assert corpo['os_entregues'] == 1 and corpo['ticket_medio_centavos'] == 4000
    assert corpo['a_receber_centavos'] == 17000


def test_resumo_mes_sem_movimento(c, dados_mes):
    corpo = _resumo(c, mes='2025-12').get_json()
    assert corpo == {'mes': '2025-12', 'faturado_centavos': 0, 'por_forma': {}, 'os_entregues': 0,
                     'ticket_medio_centavos': 0, 'a_receber_centavos': 17000}


def test_resumo_padrao_e_o_mes_corrente(c):
    os_id = _pronta(c, 10000)
    _pagar(c, os_id, 2500)
    corpo = _resumo(c).get_json()
    assert corpo['mes'] == ordens.agora().strftime('%Y-%m')
    assert corpo['faturado_centavos'] == 2500 and corpo['a_receber_centavos'] == 7500


@pytest.mark.parametrize('mes', ['2026-13', '2026-3', '03-2026', '2026-00', 'abc', '2026-03-01'])
def test_resumo_mes_invalido_400(c, mes):
    assert _resumo(c, mes=mes).status_code == 400


def test_resumo_mecanico_e_cliente_403(c):
    for uid in (c.mec1, c.cli):
        assert _resumo(c, uid).status_code == 403


def test_resumo_isolado_por_oficina(c, dados_mes):
    corpo = _resumo(c, c.dono_b, mes='2026-03').get_json()
    assert corpo['faturado_centavos'] == 1234 and corpo['os_entregues'] == 1
    assert corpo['a_receber_centavos'] == 50000 - 1234


# --- swagger -------------------------------------------------------------------------

def test_swagger_financeiro_tem_as_5_rotas_e_elas_existem():
    import re

    from backend import swagger_financeiro
    from backend.app import app
    documentadas = {(p, m.upper()) for p, ops in swagger_financeiro.PATHS.items() for m in ops}
    assert documentadas == {
        ('/api/veiculos/{veiculo_id}/historico', 'GET'),
        ('/api/os/{os_id}/pagamentos', 'GET'),
        ('/api/os/{os_id}/pagamentos', 'POST'),
        ('/api/os/{os_id}/pagamentos/{pagamento_id}', 'DELETE'),
        ('/api/financeiro/resumo', 'GET'),
    }
    reais = {(re.sub(r'<(?:\w+:)?(\w+)>', r'{\1}', r.rule), m) for r in app.url_map.iter_rules() for m in r.methods}
    assert documentadas <= reais
    assert any(t['name'] == 'Histórico e Financeiro' for t in swagger_financeiro.TAGS)
