"""Fase 0 do OficinaOS v2: ganchos em backend/ordens.py usados por orçamento, pagamentos e histórico."""
from __future__ import annotations

from datetime import date

import pytest

from backend import ordens
from backend.models import Orcamento, OrdemServico
from tests.test_ordens import Cenario


@pytest.fixture
def c(gw):
    return Cenario(gw)


def _orcamento(c, os_id, status='enviado', desconto=0, subtotal=10000, versao=1):
    with c.gw.scope() as db:
        o = Orcamento(os_id=os_id, versao=versao, status=status, itens_json='[]', subtotal_centavos=subtotal,
                      desconto_centavos=desconto, total_centavos=subtotal - desconto, validade_ate=date(2099, 1, 1),
                      token_hash=f'{os_id:064d}'[:60] + f'{versao:04d}', criado_por=c.dono)
        db.add(o)
        db.flush()
        return o.id


# --- km de entrada -----------------------------------------------------------

def test_km_de_entrada_na_abertura_e_na_edicao(c):
    os_ = c.abrir(km_entrada=45210)
    assert os_['km_entrada'] == 45210
    r = c.req('put', f'/api/os/{os_["id"]}', c.dono, json={'km_entrada': 45300})
    assert r.get_json()['ordem']['km_entrada'] == 45300
    assert c.abrir()['km_entrada'] is None


@pytest.mark.parametrize('km', [-1, 2_000_001, 'muito', 10.5, True])
def test_km_invalido_400(c, km):
    r = c.req('post', '/api/os', c.dono, json={'veiculo_id': c.v_cli, 'descricao': 'Revisão', 'km_entrada': km})
    assert r.status_code == 400


# --- entregue_em -------------------------------------------------------------

def test_entregue_em_e_gravado_na_entrega(c):
    os_ = c.abrir()
    c.item(os_['id'])
    for destino in ('orcamento_aprovado', 'em_servico', 'pronta'):
        assert c.status(os_['id'], c.dono, destino).status_code == 200
    with c.gw.scope() as db:
        assert db.get(OrdemServico, os_['id']).entregue_em is None
    r = c.status(os_['id'], c.dono, 'entregue')
    assert r.status_code == 200 and r.get_json()['ordem']['entregue_em']


# --- guarda: com orçamento, aprova-se pelo orçamento -------------------------

def test_com_orcamento_a_aprovacao_direta_por_status_e_409(c):
    os_ = c.abrir()
    c.item(os_['id'])
    _orcamento(c, os_['id'])
    r = c.status(os_['id'], c.cli, 'orcamento_aprovado')
    assert r.status_code == 409 and 'orçamento' in r.get_json()['error']
    assert c.status(os_['id'], c.dono, 'orcamento_aprovado').status_code == 409


def test_sem_orcamento_a_aprovacao_por_status_continua_valendo(c):
    os_ = c.abrir()
    c.item(os_['id'])
    assert c.status(os_['id'], c.cli, 'orcamento_aprovado').status_code == 200


def test_orcamento_status_aparece_na_os(c):
    os_ = c.abrir()
    assert c.req('get', f'/api/os/{os_["id"]}', c.dono).get_json()['ordem']['orcamento_status'] is None
    _orcamento(c, os_['id'], status='substituido', versao=1)
    _orcamento(c, os_['id'], status='enviado', versao=2)
    assert c.req('get', f'/api/os/{os_["id"]}', c.dono).get_json()['ordem']['orcamento_status'] == 'enviado'


# --- helpers para os módulos novos -------------------------------------------

def test_valor_devido_desconta_o_orcamento_aprovado(c):
    os_ = c.abrir()
    c.item(os_['id'], valor=10000)
    with c.gw.scope() as db:
        assert ordens.valor_devido(db, db.get(OrdemServico, os_['id'])) == 10000
    _orcamento(c, os_['id'], status='aprovado', desconto=1500)
    c.item(os_['id'], valor=2000)                     # peça a mais depois da aprovação
    with c.gw.scope() as db:
        assert ordens.valor_devido(db, db.get(OrdemServico, os_['id'])) == 12000 - 1500


def test_transicionar_reaproveita_regras_e_eventos(c):
    os_ = c.abrir()
    c.item(os_['id'])
    _orcamento(c, os_['id'])
    usuario_link = {'id': None, 'role': 'cliente', 'oficina_id': c.of_a}
    with c.gw.scope() as db:
        o = db.get(OrdemServico, os_['id'])
        assert ordens.transicionar(db, o, 'em_servico', usuario_link) == (
            "Transição inválida: 'aberta' não pode ir para 'em_servico'.", 409)
        assert ordens.transicionar(db, o, 'orcamento_aprovado', usuario_link, via_orcamento=True) is None
        assert o.status == 'orcamento_aprovado'
    ordens.log_transicao(usuario_link, os_['id'], 'aberta', 'orcamento_aprovado')
    eventos = [(e['acao'], e['oficina_id']) for e in c.gw.eventos]
    assert ('os.orcamento_aprovado', c.of_a) in eventos and ('os.status_alterado', c.of_a) in eventos


def test_transicionar_sem_permissao_do_papel_e_403_e_registra(c):
    os_ = c.abrir()
    c.item(os_['id'])
    mec = {'id': c.mec1, 'role': 'mecanico', 'oficina_id': c.of_a}
    with c.gw.scope() as db:
        erro = ordens.transicionar(db, db.get(OrdemServico, os_['id']), 'orcamento_aprovado', mec)
    assert erro[1] == 403 and any(e['acao'] == 'acesso_negado' for e in c.gw.eventos)
