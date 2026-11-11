"""Ordens de serviço: CRUD, itens, status, papéis, isolamento e limite do plano Free."""
from __future__ import annotations

from datetime import datetime

import pytest

from backend import ordens
from backend.models import Cliente, Oficina, OrdemServico, Veiculo


class Cenario:
    """Duas oficinas; a A tem dono, 2 mecânicos, cliente (com veículo) e um veículo de outro cliente."""

    def __init__(self, gw):
        self.gw = gw
        with gw.scope() as db:
            a, b = Oficina(nome='A', codigo_convite='A'), Oficina(nome='B', codigo_convite='B')
            db.add_all([a, b])
            db.flush()
            self.of_a, self.of_b = a.id, b.id
        au = gw.auth
        self.dono = au.add('dono', self.of_a)
        self.mec1 = au.add('mecanico', self.of_a)
        self.mec2 = au.add('mecanico', self.of_a)
        self.cli = au.add('cliente', self.of_a)
        self.dono_b = au.add('dono', self.of_b)
        self.mec_b = au.add('mecanico', self.of_b)
        self.admin = au.add('admin', None)
        with gw.scope() as db:
            c_cli = Cliente(oficina_id=self.of_a, usuario_id=self.cli, nome='Marina')
            c_out = Cliente(oficina_id=self.of_a, nome='Outro')
            c_b = Cliente(oficina_id=self.of_b, nome='Da B')
            db.add_all([c_cli, c_out, c_b])
            db.flush()
            v1 = Veiculo(oficina_id=self.of_a, cliente_id=c_cli.id, placa='MAR1N01', marca='M', modelo='X')
            v2 = Veiculo(oficina_id=self.of_a, cliente_id=c_out.id, placa='OUT1R01', marca='M', modelo='Y')
            v3 = Veiculo(oficina_id=self.of_b, cliente_id=c_b.id, placa='BBB1B11', marca='M', modelo='Z')
            db.add_all([v1, v2, v3])
            db.flush()
            self.v_cli, self.v_out, self.v_b = v1.id, v2.id, v3.id

    def req(self, metodo, url, uid, **kw):
        return getattr(self.gw.client, metodo)(url, headers={'X-Test-User': str(uid)}, **kw)

    def abrir(self, uid=None, veiculo=None, **extra):
        r = self.req('post', '/api/os', uid or self.dono, json={'veiculo_id': veiculo or self.v_cli,
                                                                 'descricao': 'Barulho no freio', **extra})
        assert r.status_code == 201, r.get_json()
        return r.get_json()['ordem']

    def item(self, os_id, uid=None, valor=10000, qtd=1):
        return self.req('post', f'/api/os/{os_id}/itens', uid or self.dono, json={
            'tipo': 'peca', 'descricao': 'Pastilha', 'quantidade': qtd, 'valor_unitario_centavos': valor})

    def status(self, os_id, uid, destino):
        return self.req('post', f'/api/os/{os_id}/status', uid, json={'status': destino})


@pytest.fixture
def c(gw):
    return Cenario(gw)


# --- CRUD -------------------------------------------------------------------

def test_crud_completo_da_os(c):
    os_ = c.abrir()
    assert os_['status'] == 'aberta' and os_['veiculo']['placa'] == 'MAR1N01'
    assert c.req('get', f'/api/os/{os_["id"]}', c.dono).status_code == 200
    assert len(c.req('get', '/api/os', c.dono).get_json()['ordens']) == 1
    r = c.req('put', f'/api/os/{os_["id"]}', c.dono, json={'descricao': 'Troca de pastilhas', 'mecanico_id': c.mec1})
    assert r.get_json()['ordem']['descricao'] == 'Troca de pastilhas' and r.get_json()['ordem']['mecanico_id'] == c.mec1
    assert c.req('delete', f'/api/os/{os_["id"]}', c.dono).status_code == 200
    assert c.req('get', f'/api/os/{os_["id"]}', c.dono).status_code == 404
    assert c.req('get', '/api/os', c.dono).get_json()['ordens'] == []
    acoes = [e['acao'] for e in c.gw.eventos]
    assert {'os.aberta', 'os.editada', 'os.excluida'} <= set(acoes)


def test_exclusao_e_logica(c):
    os_ = c.abrir()
    c.req('delete', f'/api/os/{os_["id"]}', c.dono)
    with c.gw.scope() as db:
        assert db.get(OrdemServico, os_['id']).excluida_em is not None


def test_total_e_a_soma_dos_itens(c):
    os_ = c.abrir()
    c.item(os_['id'], valor=4500, qtd=4)
    r = c.item(os_['id'], valor=3500)
    ordem = r.get_json()['ordem']
    assert ordem['valor_total_centavos'] == 21500 and len(ordem['itens']) == 2
    remover = c.req('delete', f'/api/os/{os_["id"]}/itens/{ordem["itens"][0]["id"]}', c.dono)
    assert remover.get_json()['ordem']['valor_total_centavos'] == 3500
    assert any(e['acao'] == 'os.item_adicionado' for e in c.gw.eventos)


@pytest.mark.parametrize('corpo', [
    {'tipo': 'brinde', 'descricao': 'x', 'valor_unitario_centavos': 1},
    {'tipo': 'peca', 'descricao': '', 'valor_unitario_centavos': 1},
    {'tipo': 'peca', 'descricao': 'x', 'valor_unitario_centavos': -5},
    {'tipo': 'peca', 'descricao': 'x', 'valor_unitario_centavos': 10.5},
    {'tipo': 'peca', 'descricao': 'x', 'quantidade': 0, 'valor_unitario_centavos': 1},
])
def test_item_invalido_400(c, corpo):
    os_ = c.abrir()
    assert c.req('post', f'/api/os/{os_["id"]}/itens', c.dono, json=corpo).status_code == 400


def test_descricao_curta_e_veiculo_inexistente(c):
    assert c.req('post', '/api/os', c.dono, json={'veiculo_id': c.v_cli, 'descricao': 'ab'}).status_code == 400
    assert c.req('post', '/api/os', c.dono, json={'veiculo_id': 99999, 'descricao': 'Revisão'}).status_code == 404


# --- papéis -----------------------------------------------------------------

def test_mecanico_excluindo_os_403_na_api(c):
    os_ = c.abrir(mecanico_id=c.mec1)
    r = c.req('delete', f'/api/os/{os_["id"]}', c.mec1)
    assert r.status_code == 403
    assert any(e['acao'] == 'acesso_negado' and e['usuario_id'] == c.mec1 for e in c.gw.eventos)
    assert c.req('get', f'/api/os/{os_["id"]}', c.dono).status_code == 200


def test_cliente_e_admin_nao_abrem_os(c):
    for uid in (c.cli, c.admin):
        r = c.req('post', '/api/os', uid, json={'veiculo_id': c.v_cli, 'descricao': 'Revisão geral'})
        assert r.status_code == 403


def test_mecanico_abre_os_e_fica_atribuido_a_ele(c):
    os_ = c.abrir(uid=c.mec1)
    assert os_['mecanico_id'] == c.mec1
    # mesmo que tente atribuir a outro, vale ele mesmo
    outra = c.abrir(uid=c.mec1, mecanico_id=c.mec2)
    assert outra['mecanico_id'] == c.mec1


def test_mecanico_so_ve_as_os_atribuidas_a_ele(c):
    minha = c.abrir(mecanico_id=c.mec1)
    alheia = c.abrir(mecanico_id=c.mec2)
    ids = [o['id'] for o in c.req('get', '/api/os', c.mec1).get_json()['ordens']]
    assert ids == [minha['id']]
    for metodo, extra in (('get', {}), ('put', {'json': {'descricao': 'invadindo'}}),
                          ('post', {'json': {'tipo': 'peca', 'descricao': 'x', 'valor_unitario_centavos': 1}})):
        url = f'/api/os/{alheia["id"]}' + ('/itens' if metodo == 'post' else '')
        assert getattr(c.gw.client, metodo)(url, headers={'X-Test-User': str(c.mec1)}, **extra).status_code == 404


def test_cliente_so_ve_as_proprias_os(c):
    minha = c.abrir(veiculo=c.v_cli)
    alheia = c.abrir(veiculo=c.v_out)
    ids = [o['id'] for o in c.req('get', '/api/os', c.cli).get_json()['ordens']]
    assert ids == [minha['id']]
    assert c.req('get', f'/api/os/{alheia["id"]}', c.cli).status_code == 404
    assert c.req('get', f'/api/os/{minha["id"]}', c.cli).status_code == 200


def test_dono_so_atribui_mecanico_da_propria_oficina(c):
    os_ = c.abrir()
    assert c.req('put', f'/api/os/{os_["id"]}', c.dono, json={'mecanico_id': c.mec_b}).status_code == 404
    assert c.req('put', f'/api/os/{os_["id"]}', c.dono, json={'mecanico_id': c.cli}).status_code == 404
    assert c.req('put', f'/api/os/{os_["id"]}', c.mec1, json={'mecanico_id': c.mec1}).status_code in (403, 404)


# --- isolamento por oficina -------------------------------------------------

def test_os_de_outra_oficina_404_em_todas_as_rotas(c):
    os_ = c.abrir()
    i = os_['id']
    chamadas = [('get', f'/api/os/{i}', None), ('put', f'/api/os/{i}', {'descricao': 'hack hack'}),
                ('delete', f'/api/os/{i}', None), ('post', f'/api/os/{i}/status', {'status': 'cancelada'}),
                ('post', f'/api/os/{i}/itens', {'tipo': 'peca', 'descricao': 'x', 'valor_unitario_centavos': 1})]
    for metodo, url, corpo in chamadas:
        kw = {'json': corpo} if corpo else {}
        assert c.req(metodo, url, c.dono_b, **kw).status_code == 404, (metodo, url)
    assert c.req('get', '/api/os', c.dono_b).get_json()['ordens'] == []
    assert any(e['acao'] == 'acesso_negado' and e['usuario_id'] == c.dono_b for e in c.gw.eventos)


def test_abrir_os_com_veiculo_de_outra_oficina_404(c):
    r = c.req('post', '/api/os', c.dono, json={'veiculo_id': c.v_b, 'descricao': 'Revisão geral'})
    assert r.status_code == 404


# --- máquina de estados -----------------------------------------------------

def _ate_em_servico(c):
    os_ = c.abrir(mecanico_id=c.mec1)
    c.item(os_['id'])
    assert c.status(os_['id'], c.cli, 'orcamento_aprovado').status_code == 200
    assert c.status(os_['id'], c.mec1, 'em_servico').status_code == 200
    return os_['id']


def test_fluxo_feliz_de_status(c):
    i = _ate_em_servico(c)
    assert c.status(i, c.mec1, 'pronta').status_code == 200
    assert c.status(i, c.dono, 'entregue').status_code == 200
    acoes = [e['acao'] for e in c.gw.eventos]
    assert acoes.count('os.status_alterado') == 4
    assert {'os.orcamento_aprovado', 'os.entregue'} <= set(acoes)


@pytest.mark.parametrize('de_para', [('aberta', 'pronta'), ('aberta', 'entregue'), ('aberta', 'em_servico'),
                                     ('aberta', 'inexistente')])
def test_transicao_invalida_409(c, de_para):
    os_ = c.abrir()
    assert c.status(os_['id'], c.dono, de_para[1]).status_code == 409


def test_status_final_nao_volta(c):
    i = _ate_em_servico(c)
    c.status(i, c.mec1, 'pronta')
    c.status(i, c.dono, 'entregue')
    assert c.status(i, c.dono, 'cancelada').status_code == 409
    assert c.status(i, c.dono, 'aberta').status_code == 409
    assert c.req('put', f'/api/os/{i}', c.dono, json={'descricao': 'depois de entregue'}).status_code == 409


def test_aprovar_orcamento_so_cliente_ou_dono(c):
    os_ = c.abrir(mecanico_id=c.mec1)
    c.item(os_['id'])
    assert c.status(os_['id'], c.mec1, 'orcamento_aprovado').status_code == 403
    assert c.status(os_['id'], c.cli, 'orcamento_aprovado').status_code == 200


def test_cliente_de_outro_veiculo_nao_aprova(c):
    os_ = c.abrir(veiculo=c.v_out)
    c.item(os_['id'])
    assert c.status(os_['id'], c.cli, 'orcamento_aprovado').status_code == 404


def test_orcamento_sem_itens_nao_pode_ser_aprovado(c):
    os_ = c.abrir()
    assert c.status(os_['id'], c.dono, 'orcamento_aprovado').status_code == 409


def test_entregar_e_cancelar_so_o_dono(c):
    i = _ate_em_servico(c)
    c.status(i, c.mec1, 'pronta')
    assert c.status(i, c.mec1, 'entregue').status_code == 403
    assert c.status(i, c.mec1, 'cancelada').status_code == 403
    assert c.status(i, c.dono, 'cancelada').status_code == 200
    assert any(e['acao'] == 'os.cancelada' for e in c.gw.eventos)


def test_itens_travados_depois_de_pronta(c):
    i = _ate_em_servico(c)
    c.status(i, c.mec1, 'pronta')
    assert c.item(i).status_code == 409


# --- limite do plano Free (20 OS por mês) -----------------------------------

def test_21a_os_do_mes_no_free_recebe_402(c):
    for _ in range(20):
        c.abrir()
    r = c.req('post', '/api/os', c.dono, json={'veiculo_id': c.v_cli, 'descricao': 'A 21ª ordem'})
    assert r.status_code == 402
    corpo = r.get_json()
    assert corpo['codigo'] == 'limite_plano' and corpo['limite'] == 20 and corpo['uso'] == 20
    assert corpo['plano'] == 'free' and 'Pro' in corpo['como_liberar']
    assert any(e['acao'] == 'plano.limite_atingido' for e in c.gw.eventos)


def test_excluir_nao_devolve_cota(c):
    ids = [c.abrir()['id'] for _ in range(20)]
    c.req('delete', f'/api/os/{ids[0]}', c.dono)
    assert c.req('post', '/api/os', c.dono, json={'veiculo_id': c.v_cli, 'descricao': 'Mais uma'}).status_code == 402


def test_cota_e_por_oficina(c):
    for _ in range(20):
        c.abrir()
    r = c.req('post', '/api/os', c.dono_b, json={'veiculo_id': c.v_b, 'descricao': 'Outra oficina'})
    assert r.status_code == 201


def test_cota_zera_no_mes_seguinte(c, monkeypatch):
    for _ in range(20):
        c.abrir()
    mes_que_vem = ordens.agora().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    proximo = datetime(mes_que_vem.year + (mes_que_vem.month == 12), mes_que_vem.month % 12 + 1, 2, 10, 0)
    monkeypatch.setattr(ordens, 'agora', lambda: proximo)
    assert c.req('post', '/api/os', c.dono, json={'veiculo_id': c.v_cli, 'descricao': 'Mês novo'}).status_code == 201


def test_plano_pro_nao_tem_limite(c, monkeypatch):
    from backend import planos
    monkeypatch.setattr(planos, 'plano_da_oficina', lambda _id: 'pro')
    for _ in range(21):
        c.abrir()
    assert len(c.req('get', '/api/os', c.dono).get_json()['ordens']) == 21


def test_decisao_de_limite_nao_chama_a_stripe(c, monkeypatch):
    """A decisão vem do banco/constante, nunca de chamada externa."""
    import requests
    monkeypatch.setattr(requests, 'post', lambda *a, **k: (_ for _ in ()).throw(AssertionError('chamou a rede')))
    monkeypatch.setattr(requests, 'get', lambda *a, **k: (_ for _ in ()).throw(AssertionError('chamou a rede')))
    for _ in range(20):
        c.abrir()
    assert c.req('post', '/api/os', c.dono, json={'veiculo_id': c.v_cli, 'descricao': 'Bloqueada'}).status_code == 402
