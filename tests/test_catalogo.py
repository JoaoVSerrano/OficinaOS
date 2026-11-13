"""Catálogo de serviços e peças (tabela de preços da oficina): CRUD, papéis, escopo e Swagger."""
from __future__ import annotations

import re

import pytest

from backend.models import CatalogoItem
from tests.test_ordens import Cenario


@pytest.fixture
def c(gw):
    return Cenario(gw)


def _criar(c, uid=None, **campos):
    corpo = {'tipo': 'servico', 'descricao': 'Troca de óleo', 'valor_centavos': 8000, **campos}
    return c.req('post', '/api/catalogo', uid or c.dono, json=corpo)


def _novo(c, **campos):
    r = _criar(c, **campos)
    assert r.status_code == 201, r.get_json()
    return r.get_json()['item']


def _item_da_b(c, ativo=True):
    with c.gw.scope() as db:
        item = CatalogoItem(oficina_id=c.of_b, tipo='peca', descricao='Peça da B', valor_centavos=999, ativo=ativo)
        db.add(item)
        db.flush()
        return item.id


def _listar(c, uid, query=''):
    r = c.req('get', '/api/catalogo' + query, uid)
    assert r.status_code == 200, r.get_json()
    return r.get_json()['itens']


# --- CRUD do dono -------------------------------------------------------------

def test_crud_e_desativacao_pelo_dono(c):
    item = _novo(c, descricao='  Alinhamento  ', valor_centavos=12000)
    assert item == {'id': item['id'], 'tipo': 'servico', 'descricao': 'Alinhamento', 'valor_centavos': 12000,
                    'ativo': True}
    assert _listar(c, c.dono) == [item]

    r = c.req('put', f'/api/catalogo/{item["id"]}', c.dono, json={'valor_centavos': 13000})
    assert r.status_code == 200
    assert r.get_json()['item']['valor_centavos'] == 13000
    assert r.get_json()['item']['descricao'] == 'Alinhamento'

    r = c.req('delete', f'/api/catalogo/{item["id"]}', c.dono)
    assert r.status_code == 200
    with c.gw.scope() as db:
        registro = db.get(CatalogoItem, item['id'])
        assert registro is not None and registro.ativo is False
    assert _listar(c, c.dono) == []

    r = c.req('put', f'/api/catalogo/{item["id"]}', c.dono, json={'ativo': True})
    assert r.status_code == 200 and r.get_json()['item']['ativo'] is True
    assert [i['id'] for i in _listar(c, c.dono)] == [item['id']]


def test_lista_ordenada_por_tipo_e_descricao_e_filtro_por_tipo(c):
    _novo(c, tipo='servico', descricao='Revisão')
    _novo(c, tipo='peca', descricao='Pastilha')
    _novo(c, tipo='servico', descricao='Alinhamento')
    _novo(c, tipo='peca', descricao='Filtro de óleo')
    assert [(i['tipo'], i['descricao']) for i in _listar(c, c.dono)] == [
        ('peca', 'Filtro de óleo'), ('peca', 'Pastilha'), ('servico', 'Alinhamento'), ('servico', 'Revisão')]
    assert [i['descricao'] for i in _listar(c, c.mec1, '?tipo=servico')] == ['Alinhamento', 'Revisão']
    assert [i['descricao'] for i in _listar(c, c.dono, '?tipo=peca')] == ['Filtro de óleo', 'Pastilha']


# --- papéis -------------------------------------------------------------------

def test_mecanico_le_so_ativos_e_nao_altera(c):
    ativo = _novo(c, descricao='Ativo')
    inativo = _novo(c, descricao='Inativo')
    c.req('delete', f'/api/catalogo/{inativo["id"]}', c.dono)

    assert [i['id'] for i in _listar(c, c.mec1)] == [ativo['id']]
    assert [i['id'] for i in _listar(c, c.mec1, '?todos=1')] == [ativo['id']]
    assert _criar(c, c.mec1).status_code == 403
    assert c.req('put', f'/api/catalogo/{ativo["id"]}', c.mec1, json={'valor_centavos': 1}).status_code == 403
    assert c.req('delete', f'/api/catalogo/{ativo["id"]}', c.mec1).status_code == 403


def test_todos_mostra_inativos_so_ao_dono(c):
    ativo = _novo(c, descricao='Ativo')
    inativo = _novo(c, descricao='Inativo')
    c.req('delete', f'/api/catalogo/{inativo["id"]}', c.dono)
    itens = _listar(c, c.dono, '?todos=1')
    assert {i['id']: i['ativo'] for i in itens} == {ativo['id']: True, inativo['id']: False}


@pytest.mark.parametrize('papel', ['cli', 'admin'])
def test_cliente_e_admin_recebem_403(c, papel):
    uid = getattr(c, papel)
    item = _novo(c)
    assert c.req('get', '/api/catalogo', uid).status_code == 403
    assert _criar(c, uid).status_code == 403
    assert c.req('put', f'/api/catalogo/{item["id"]}', uid, json={'valor_centavos': 1}).status_code == 403
    assert c.req('delete', f'/api/catalogo/{item["id"]}', uid).status_code == 403


# --- escopo por oficina ---------------------------------------------------------

def test_item_de_outra_oficina_e_invisivel_e_404(c):
    id_b = _item_da_b(c)
    _novo(c, descricao='Da A')
    assert [i['descricao'] for i in _listar(c, c.dono, '?todos=1')] == ['Da A']
    assert c.req('put', f'/api/catalogo/{id_b}', c.dono, json={'valor_centavos': 1}).status_code == 404
    assert c.req('delete', f'/api/catalogo/{id_b}', c.dono).status_code == 404
    assert c.req('put', '/api/catalogo/999999', c.dono, json={'valor_centavos': 1}).status_code == 404
    with c.gw.scope() as db:
        registro = db.get(CatalogoItem, id_b)
        assert registro.valor_centavos == 999 and registro.ativo is True
    assert [i['descricao'] for i in _listar(c, c.dono_b)] == ['Peça da B']


def test_oficina_id_do_corpo_e_ignorado(c):
    item = _novo(c, oficina_id=c.of_b)
    with c.gw.scope() as db:
        assert db.get(CatalogoItem, item['id']).oficina_id == c.of_a


# --- validações ---------------------------------------------------------------

@pytest.mark.parametrize('campos', [
    {'tipo': 'outro'}, {'tipo': None}, {'descricao': '   '}, {'descricao': ''}, {'descricao': 'x' * 256},
    {'valor_centavos': -1}, {'valor_centavos': 10.5}, {'valor_centavos': True}, {'valor_centavos': '100'},
    {'valor_centavos': 100_000_001},
])
def test_validacoes_na_criacao_400(c, campos):
    r = _criar(c, **campos)
    assert r.status_code == 400 and r.get_json()['error']


@pytest.mark.parametrize('campos', [
    {'tipo': 'outro'}, {'descricao': '  '}, {'valor_centavos': -1}, {'valor_centavos': 1.5},
    {'valor_centavos': False}, {'ativo': 'sim'}, {'ativo': 1},
])
def test_validacoes_na_edicao_400(c, campos):
    item = _novo(c)
    r = c.req('put', f'/api/catalogo/{item["id"]}', c.dono, json=campos)
    assert r.status_code == 400 and r.get_json()['error']


def test_limites_validos(c):
    assert _novo(c, valor_centavos=0)['valor_centavos'] == 0
    assert _novo(c, valor_centavos=100_000_000, descricao='y' * 255)['valor_centavos'] == 100_000_000


# --- log -----------------------------------------------------------------------

def test_eventos_de_log_com_a_oficina_certa(c):
    item = _novo(c)
    c.req('put', f'/api/catalogo/{item["id"]}', c.dono, json={'descricao': 'Troca de óleo e filtro'})
    c.req('delete', f'/api/catalogo/{item["id"]}', c.dono)
    eventos = {e['acao']: e for e in c.gw.eventos if e['acao'].startswith('catalogo.')}
    assert set(eventos) == {'catalogo.item_criado', 'catalogo.item_editado', 'catalogo.item_desativado'}
    for e in eventos.values():
        assert e['oficina_id'] == c.of_a and e['recurso'] == 'catalogo_item' and e['recurso_id'] == item['id']
    assert all(e['acao'] != 'catalogo.item_criado' for e in c.gw.eventos if e['oficina_id'] == c.of_b)


# --- Swagger ------------------------------------------------------------------

def test_swagger_catalogo_tem_as_4_rotas_registradas():
    from backend import swagger_catalogo
    from backend.app import app
    spec = {(p, m) for p, item in swagger_catalogo.PATHS.items() for m in item if m in ('get', 'post', 'put', 'delete')}
    assert spec == {('/api/catalogo', 'get'), ('/api/catalogo', 'post'),
                    ('/api/catalogo/{item_id}', 'put'), ('/api/catalogo/{item_id}', 'delete')}
    reais = {(re.sub(r'<(?:\w+:)?(\w+)>', r'{\1}', r.rule), m.lower())
             for r in app.url_map.iter_rules() for m in r.methods - {'HEAD', 'OPTIONS'}}
    assert spec <= reais
    assert any(t['name'] == 'Catálogo' for t in swagger_catalogo.TAGS)
