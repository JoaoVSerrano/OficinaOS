"""Orçamento com versões, decisão pelo app e pelo link público, e anotações internas da OS."""
from __future__ import annotations

import hashlib
from datetime import timedelta

import pytest

from backend import ordens, swagger_orcamentos
from backend.models import Orcamento, OrdemServico
from tests.test_ordens import Cenario


@pytest.fixture
def c(gw):
    return Cenario(gw)


def _os_com_item(c, valor=10000, **extra):
    os_ = c.abrir(**extra)
    assert c.item(os_['id'], valor=valor).status_code == 201
    return os_['id']


def _enviar(c, os_id, uid=None, **corpo):
    return c.req('post', f'/api/os/{os_id}/orcamentos', uid or c.dono, json=corpo)


def _enviado(c, os_id, **corpo):
    r = _enviar(c, os_id, **corpo)
    assert r.status_code == 201, r.get_json()
    dados = r.get_json()
    return dados['orcamento'], dados['link'].rsplit('/', 1)[-1]


def _decidir(c, os_id, orc_id, uid, **corpo):
    return c.req('post', f'/api/os/{os_id}/orcamentos/{orc_id}/decisao', uid, json=corpo)


def _pub(c, token, metodo='get', **kw):
    return getattr(c.gw.client, metodo)(f'/api/publico/orcamentos/{token}' + ('/decisao' if metodo == 'post' else ''),
                                        **kw)


def _expirar(c, orc_id):
    with c.gw.scope() as db:
        db.get(Orcamento, orc_id).validade_ate = ordens.agora().date() - timedelta(days=1)


def _acoes(c):
    return [e['acao'] for e in c.gw.eventos]


# --- envio -------------------------------------------------------------------

def test_envio_cria_versao_com_snapshot_e_link_relativo(c):
    os_id = _os_com_item(c, valor=25000)
    r = _enviar(c, os_id, desconto_centavos=5000, validade_dias=10, observacoes_cliente='Peças originais')
    assert r.status_code == 201
    dados = r.get_json()
    assert dados['link'].startswith('/orcamento/') and len(dados['link']) > len('/orcamento/') + 30
    o = dados['orcamento']
    assert (o['versao'], o['status'], o['expirado']) == (1, 'enviado', False)
    assert (o['subtotal_centavos'], o['desconto_centavos'], o['total_centavos']) == (25000, 5000, 20000)
    assert o['validade_ate'] == (ordens.agora().date() + timedelta(days=10)).isoformat()
    assert o['itens'] == [{'tipo': 'peca', 'descricao': 'Pastilha', 'quantidade': 1, 'valor_unitario_centavos': 25000,
                           'subtotal_centavos': 25000}]
    assert o['observacoes_cliente'] == 'Peças originais'
    ev = [e for e in c.gw.eventos if e['acao'] == 'orcamento.enviado']
    assert ev and ev[0]['detalhe']['versao'] == 1 and ev[0]['detalhe']['total_centavos'] == 20000


def test_so_o_dono_envia(c):
    os_id = _os_com_item(c, mecanico_id=c.mec1)
    assert _enviar(c, os_id, c.mec1).status_code == 403
    assert _enviar(c, os_id, c.cli).status_code == 403


def test_subtotal_zero_409(c):
    os_ = c.abrir()
    assert _enviar(c, os_['id']).status_code == 409


@pytest.mark.parametrize('corpo', [
    {'desconto_centavos': 10001}, {'desconto_centavos': -1}, {'desconto_centavos': 10.5},
    {'desconto_centavos': True}, {'validade_dias': 0}, {'validade_dias': 91}, {'validade_dias': '7'},
    {'observacoes_cliente': 'x' * 2001},
])
def test_envio_invalido_400(c, corpo):
    os_id = _os_com_item(c)
    assert _enviar(c, os_id, **corpo).status_code == 400


def test_envio_fora_de_aberta_409_e_outra_oficina_404(c):
    os_id = _os_com_item(c)
    assert _enviar(c, os_id, c.dono_b).status_code == 404
    c.status(os_id, c.dono, 'orcamento_aprovado')
    assert _enviar(c, os_id).status_code == 409


def test_segunda_versao_substitui_a_primeira(c):
    os_id = _os_com_item(c)
    v1, _ = _enviado(c, os_id)
    v2, _ = _enviado(c, os_id)
    assert v2['versao'] == 2
    lista = c.req('get', f'/api/os/{os_id}/orcamentos', c.dono).get_json()['orcamentos']
    assert [(o['versao'], o['status']) for o in lista] == [(2, 'enviado'), (1, 'substituido')]
    assert c.req('get', f'/api/os/{os_id}', c.dono).get_json()['ordem']['orcamento_status'] == 'enviado'


def test_banco_guarda_so_o_hash(c):
    os_id = _os_com_item(c)
    orc, token = _enviado(c, os_id)
    with c.gw.scope() as db:
        o = db.get(Orcamento, orc['id'])
        valores = [str(getattr(o, col.key)) for col in Orcamento.__table__.columns]
        assert o.token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert not any(token in v for v in valores)


def test_listagem_nunca_expoe_token_nem_hash(c):
    os_id = _os_com_item(c)
    orc, token = _enviado(c, os_id)
    with c.gw.scope() as db:
        hash_ = db.get(Orcamento, orc['id']).token_hash
    for uid in (c.dono, c.cli):
        r = c.req('get', f'/api/os/{os_id}/orcamentos', uid)
        assert r.status_code == 200
        texto = r.get_data(as_text=True)
        assert token not in texto and hash_ not in texto and 'token' not in texto


def test_listagem_respeita_visibilidade(c):
    os_id = _os_com_item(c, veiculo=c.v_out)
    _enviado(c, os_id)
    assert c.req('get', f'/api/os/{os_id}/orcamentos', c.cli).status_code == 404
    assert c.req('get', f'/api/os/{os_id}/orcamentos', c.mec1).status_code == 404
    assert c.req('get', f'/api/os/{os_id}/orcamentos', c.dono_b).status_code == 404


# --- decisão pelo app ----------------------------------------------------------

def test_cliente_aprova_pelo_app(c):
    os_id = _os_com_item(c)
    orc, _ = _enviado(c, os_id)
    r = _decidir(c, os_id, orc['id'], c.cli, acao='aprovar')
    assert r.status_code == 200, r.get_json()
    assert r.get_json()['orcamento']['status'] == 'aprovado'
    assert c.req('get', f'/api/os/{os_id}', c.dono).get_json()['ordem']['status'] == 'orcamento_aprovado'
    assert {'orcamento.aprovado', 'os.orcamento_aprovado'} <= set(_acoes(c))
    with c.gw.scope() as db:
        o = db.get(Orcamento, orc['id'])
        assert (o.decidido_via, o.decidido_por_usuario_id) == ('app', c.cli) and o.decidido_em


def test_dono_aprova_pelo_app(c):
    os_id = _os_com_item(c)
    orc, _ = _enviado(c, os_id)
    assert _decidir(c, os_id, orc['id'], c.dono, acao='aprovar').status_code == 200


def test_mecanico_nao_decide(c):
    os_id = _os_com_item(c, mecanico_id=c.mec1)
    orc, _ = _enviado(c, os_id)
    assert _decidir(c, os_id, orc['id'], c.mec1, acao='aprovar').status_code == 403


def test_cliente_de_outro_veiculo_e_outra_oficina_404(c):
    os_id = _os_com_item(c, veiculo=c.v_out)
    orc, _ = _enviado(c, os_id)
    assert _decidir(c, os_id, orc['id'], c.cli, acao='aprovar').status_code == 404
    assert _decidir(c, os_id, orc['id'], c.dono_b, acao='aprovar').status_code == 404


def test_orcamento_de_outra_os_404(c):
    os1 = _os_com_item(c)
    os2 = _os_com_item(c)
    orc, _ = _enviado(c, os1)
    assert _decidir(c, os2, orc['id'], c.dono, acao='aprovar').status_code == 404


def test_recusa_exige_motivo_e_mantem_a_os_aberta(c):
    os_id = _os_com_item(c)
    orc, _ = _enviado(c, os_id)
    assert _decidir(c, os_id, orc['id'], c.cli, acao='recusar').status_code == 400
    assert _decidir(c, os_id, orc['id'], c.cli, acao='recusar', motivo='ab').status_code == 400
    assert _decidir(c, os_id, orc['id'], c.cli, acao='talvez').status_code == 400
    r = _decidir(c, os_id, orc['id'], c.cli, acao='recusar', motivo='Achei caro')
    assert r.status_code == 200 and r.get_json()['orcamento']['motivo_recusa'] == 'Achei caro'
    assert c.req('get', f'/api/os/{os_id}', c.dono).get_json()['ordem']['status'] == 'aberta'
    ev = [e for e in c.gw.eventos if e['acao'] == 'orcamento.recusado']
    assert ev and ev[0]['detalhe']['motivo'] == 'Achei caro'
    # o dono ajusta e envia nova versão
    assert _enviar(c, os_id).status_code == 201


def test_aprovar_versao_substituida_ou_ja_decidida_409(c):
    os_id = _os_com_item(c)
    v1, _ = _enviado(c, os_id)
    v2, _ = _enviado(c, os_id)
    assert _decidir(c, os_id, v1['id'], c.cli, acao='aprovar').status_code == 409
    assert _decidir(c, os_id, v2['id'], c.cli, acao='recusar', motivo='Caro demais').status_code == 200
    assert _decidir(c, os_id, v2['id'], c.cli, acao='aprovar').status_code == 409


def test_aprovar_orcamento_desatualizado_409(c):
    os_id = _os_com_item(c)
    orc, _ = _enviado(c, os_id)
    c.item(os_id, valor=500)
    r = _decidir(c, os_id, orc['id'], c.cli, acao='aprovar')
    assert r.status_code == 409 and 'desatualizado' in r.get_json()['error']


def test_aprovar_expirado_410(c):
    os_id = _os_com_item(c)
    orc, _ = _enviado(c, os_id)
    _expirar(c, orc['id'])
    assert c.req('get', f'/api/os/{os_id}/orcamentos', c.dono).get_json()['orcamentos'][0]['expirado'] is True
    assert _decidir(c, os_id, orc['id'], c.cli, acao='aprovar').status_code == 410


# --- link público --------------------------------------------------------------

CHAVES_PUBLICAS = {'oficina', 'cliente', 'veiculo', 'os', 'orcamento'}


def _chaves_aninhadas(obj, prefixo=''):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _chaves_aninhadas(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _chaves_aninhadas(v)


def test_publico_get_so_devolve_o_permitido(c):
    os_id = _os_com_item(c, km_entrada=45210)
    _, token = _enviado(c, os_id, observacoes_cliente='Garantia de 90 dias')
    r = _pub(c, token)
    assert r.status_code == 200
    assert 'no-store' in r.headers['Cache-Control']
    d = r.get_json()
    assert set(d) == CHAVES_PUBLICAS
    assert set(d['oficina']) == {'nome'} and d['oficina']['nome'] == 'A'
    assert set(d['cliente']) == {'nome'} and d['cliente']['nome'] == 'Marina'
    assert set(d['veiculo']) == {'placa', 'marca', 'modelo', 'ano'}
    assert d['os'] == {'descricao': 'Barulho no freio', 'km_entrada': 45210}
    assert set(d['orcamento']) == {'versao', 'status', 'expirado', 'itens', 'subtotal_centavos', 'desconto_centavos',
                                   'total_centavos', 'validade_ate', 'observacoes_cliente', 'enviado_em',
                                   'decidido_em', 'motivo_recusa'}
    chaves = set(_chaves_aninhadas(d))
    assert not any(k == 'id' or k.endswith('_id') for k in chaves)
    assert not {'email', 'telefone', 'token', 'token_hash', 'notas'} & chaves


def test_publico_token_invalido_404_com_no_store(c):
    r = _pub(c, 'nao-existe')
    assert r.status_code == 404 and 'no-store' in r.headers['Cache-Control']
    r = _pub(c, 'nao-existe', 'post', json={'acao': 'aprovar'})
    assert r.status_code == 404 and 'no-store' in r.headers['Cache-Control']


def test_publico_os_excluida_404(c):
    os_id = _os_com_item(c)
    _, token = _enviado(c, os_id)
    c.req('delete', f'/api/os/{os_id}', c.dono)
    assert _pub(c, token).status_code == 404


def test_publico_aprova_e_evento_vai_para_a_oficina(c):
    os_id = _os_com_item(c)
    orc, token = _enviado(c, os_id)
    r = _pub(c, token, 'post', json={'acao': 'aprovar'})
    assert r.status_code == 200, r.get_json()
    assert r.get_json()['orcamento']['status'] == 'aprovado'
    with c.gw.scope() as db:
        assert db.get(OrdemServico, os_id).status == 'orcamento_aprovado'
        o = db.get(Orcamento, orc['id'])
        assert (o.decidido_via, o.decidido_por_usuario_id) == ('link', None)
    eventos = [(e['acao'], e['oficina_id']) for e in c.gw.eventos]
    assert ('orcamento.aprovado', c.of_a) in eventos and ('os.orcamento_aprovado', c.of_a) in eventos
    segunda = _pub(c, token, 'post', json={'acao': 'recusar', 'motivo': 'Mudei de ideia'})
    assert segunda.status_code == 409 and 'no-store' in segunda.headers['Cache-Control']


def test_publico_recusa_exige_motivo(c):
    os_id = _os_com_item(c)
    _, token = _enviado(c, os_id)
    assert _pub(c, token, 'post', json={'acao': 'recusar'}).status_code == 400
    r = _pub(c, token, 'post', json={'acao': 'recusar', 'motivo': 'Vou pensar'})
    assert r.status_code == 200 and r.get_json()['orcamento']['status'] == 'recusado'


def test_publico_substituido_409_e_desatualizado_409(c):
    os_id = _os_com_item(c)
    _, token1 = _enviado(c, os_id)
    _, token2 = _enviado(c, os_id)
    assert _pub(c, token1).get_json()['orcamento']['status'] == 'substituido'
    assert _pub(c, token1, 'post', json={'acao': 'aprovar'}).status_code == 409
    c.item(os_id, valor=100)
    assert _pub(c, token2, 'post', json={'acao': 'aprovar'}).status_code == 409


def test_publico_expirado_410(c):
    os_id = _os_com_item(c)
    orc, token = _enviado(c, os_id)
    _expirar(c, orc['id'])
    assert _pub(c, token).get_json()['orcamento']['expirado'] is True
    assert _pub(c, token, 'post', json={'acao': 'aprovar'}).status_code == 410


def test_publico_rate_limit_por_token(c):
    os_id = _os_com_item(c)
    _, token = _enviado(c, os_id)
    for i in range(10):
        # IP diferente a cada vez: o limite por token vale mesmo com X-Forwarded-For falsificado
        assert _pub(c, token, headers={'X-Forwarded-For': f'200.0.0.{i}'}).status_code == 200
    r = _pub(c, token, headers={'X-Forwarded-For': '200.0.0.99'})
    assert r.status_code == 429 and 'no-store' in r.headers['Cache-Control']


# --- anotações internas --------------------------------------------------------

def test_notas_dono_e_mecanico_atribuido(c):
    os_ = c.abrir(mecanico_id=c.mec1)
    url = f'/api/os/{os_["id"]}/notas'
    assert c.req('post', url, c.dono, json={'texto': 'Cliente pediu urgência'}).status_code == 201
    r = c.req('post', url, c.mec1, json={'texto': 'Disco empenado'})
    assert r.status_code == 201 and r.get_json()['nota']['autor_id'] == c.mec1
    for uid in (c.dono, c.mec1):
        notas = c.req('get', url, uid).get_json()['notas']
        assert [n['texto'] for n in notas] == ['Disco empenado', 'Cliente pediu urgência']
        assert {'id', 'autor_id', 'texto', 'criada_em'} <= set(notas[0])
    assert 'os.nota_adicionada' in _acoes(c)


def test_notas_acesso_negado(c):
    os_ = c.abrir(mecanico_id=c.mec1)
    url = f'/api/os/{os_["id"]}/notas'
    assert c.req('get', url, c.mec2).status_code == 404
    assert c.req('post', url, c.mec2, json={'texto': 'x'}).status_code == 404
    assert c.req('get', url, c.cli).status_code == 403
    assert c.req('post', url, c.cli, json={'texto': 'oi'}).status_code == 403
    assert c.req('get', url, c.dono_b).status_code == 404
    assert c.req('post', url, c.dono, json={'texto': '   '}).status_code == 400
    assert c.req('post', url, c.dono, json={'texto': 'x' * 2001}).status_code == 400


# --- documentação --------------------------------------------------------------

def test_swagger_tem_as_7_rotas_e_elas_existem():
    from backend.app import app
    import re
    documentadas = {(p, m) for p, item in swagger_orcamentos.PATHS.items() for m in item
                    if m in ('get', 'post', 'put', 'delete', 'patch')}
    assert len(documentadas) == 7
    reais = set()
    for regra in app.url_map.iter_rules():
        caminho = re.sub(r'<(?:\w+:)?(\w+)>', r'{\1}', regra.rule)
        for m in regra.methods - {'HEAD', 'OPTIONS'}:
            reais.add((caminho, m.lower()))
    assert documentadas <= reais
