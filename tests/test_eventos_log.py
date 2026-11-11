"""Eventos de negócio: o gateway registra quem/papel/oficina/recurso; o log-service guarda e filtra por oficina."""
from __future__ import annotations

import json
import os
from types import SimpleNamespace

import pytest

from tests.test_ordens import Cenario

TOKEN = {'X-Internal-Token': os.environ['INTERNAL_TOKEN']}


@pytest.fixture
def c(gw):
    return Cenario(gw)


def test_evento_de_negocio_leva_usuario_papel_oficina_e_recurso(c):
    os_ = c.abrir(uid=c.mec1)
    ev = next(e for e in c.gw.eventos if e['acao'] == 'os.aberta')
    assert ev['usuario_id'] == c.mec1
    assert ev['papel'] == 'mecanico' and ev['oficina_id'] == c.of_a
    assert ev['recurso'] == 'os' and ev['recurso_id'] == os_['id']


def test_acesso_negado_registra_403_e_404(c):
    os_ = c.abrir()
    c.req('delete', f'/api/os/{os_["id"]}', c.mec1)            # 403 por papel
    c.req('get', f'/api/os/{os_["id"]}', c.dono_b)             # 404 de outra oficina
    negados = [e for e in c.gw.eventos if e['acao'] == 'acesso_negado']
    assert {e['usuario_id'] for e in negados} == {c.mec1, c.dono_b}
    motivos = {json.loads(json.dumps(e['detalhe']))['motivo'] for e in negados}
    assert motivos == {'papel', 'nao_encontrado_na_oficina'}


def test_detalhe_do_log_nao_vaza_dado_pessoal(c):
    c.abrir()
    for e in c.gw.eventos:
        texto = json.dumps(e['detalhe']).lower()
        assert '@' not in texto and 'senha' not in texto


def test_log_event_envia_campos_de_negocio_ao_log_service(monkeypatch):
    from backend import app as core
    enviado = {}

    def falso_post(url, json=None, headers=None, timeout=None):
        enviado.update(url=url, json=json, headers=headers)
    monkeypatch.setattr(core.requests, 'post', falso_post)
    with core.app.test_request_context('/', environ_base={'REMOTE_ADDR': '10.0.0.9'}):
        core.log_event('os.aberta', usuario_id=5, detalhe={'x': 1}, oficina_id=3, papel='dono', recurso='os',
                       recurso_id=9, intruso='ignorado')
    assert enviado['json']['oficina_id'] == 3 and enviado['json']['papel'] == 'dono'
    assert enviado['json']['recurso'] == 'os' and enviado['json']['recurso_id'] == 9
    assert 'intruso' not in enviado['json']
    assert enviado['headers']['X-Internal-Token']


# --- log-service ------------------------------------------------------------

class FakeRedis:
    def __init__(self):
        self.itens: list[tuple[str, dict]] = []

    def xadd(self, chave, entry, maxlen=None, approximate=True):
        id_ = f'{len(self.itens) + 1}-0'
        self.itens.append((id_, entry))
        return id_

    def xlen(self, chave):
        return len(self.itens)

    def xrevrange(self, chave, max='+', min='-', count=None):
        return list(reversed(self.itens))[:count]


@pytest.fixture
def logsvc(monkeypatch):
    from log_service import app as log_app
    r = FakeRedis()
    monkeypatch.setattr(log_app, 'get_redis', lambda: r)
    log_app.app.config['TESTING'] = True
    with log_app.app.test_client() as cli:
        yield cli


def _gravar(cli, **corpo):
    return cli.post('/log', headers=TOKEN, json=corpo)


def test_log_service_guarda_e_devolve_campos_de_negocio(logsvc):
    assert _gravar(logsvc, acao='os.aberta', usuario_id=2, oficina_id=1, papel='dono', recurso='os',
                   recurso_id=7, detalhe='{}').status_code == 201
    log = logsvc.get('/logs', headers=TOKEN).get_json()['logs'][0]
    assert log['oficina_id'] == '1' and log['papel'] == 'dono' and log['recurso'] == 'os' and log['recurso_id'] == '7'
    assert log['ts_ms'] > 0


def test_log_service_filtra_por_oficina_e_tipo(logsvc):
    _gravar(logsvc, acao='os.aberta', usuario_id=1, oficina_id=1)
    _gravar(logsvc, acao='os.excluida', usuario_id=1, oficina_id=1)
    _gravar(logsvc, acao='os.aberta', usuario_id=9, oficina_id=2)
    _gravar(logsvc, acao='login', usuario_id=1)
    da_1 = logsvc.get('/logs?oficina_id=1', headers=TOKEN).get_json()['logs']
    assert {x['acao'] for x in da_1} == {'os.aberta', 'os.excluida'}
    assert all(x['oficina_id'] == '1' for x in da_1)
    so_abertas = logsvc.get('/logs?oficina_id=1&acao=os.aberta', headers=TOKEN).get_json()['logs']
    assert [x['acao'] for x in so_abertas] == ['os.aberta']
    assert len(logsvc.get('/logs', headers=TOKEN).get_json()['logs']) == 4   # login continua sendo registrado


def test_log_service_exige_token(logsvc):
    assert logsvc.post('/log', json={'acao': 'x'}).status_code == 403
    assert logsvc.get('/logs').status_code == 403


# --- /api/auditoria (dono) --------------------------------------------------

def test_auditoria_forca_a_oficina_do_usuario(c, monkeypatch):
    from backend import dominio
    chamadas = []

    def falso_get(url, params=None, headers=None, timeout=None):
        chamadas.append(params)
        return SimpleNamespace(raise_for_status=lambda: None,
                               json=lambda: {'logs': [{'usuario_id': str(c.dono), 'acao': 'os.aberta'}]})
    monkeypatch.setattr(dominio.requests, 'get', falso_get)
    r = c.req('get', f'/api/auditoria?oficina_id={c.of_b}&acao=os.', c.dono)
    assert r.status_code == 200
    assert chamadas[0]['oficina_id'] == c.of_a            # ignora o oficina_id da query string
    assert chamadas[0]['acao'] == 'os.'
    assert r.get_json()['logs'][0]['usuario_nome'] == f'dono{c.dono}'


def test_auditoria_so_para_dono(c):
    for uid in (c.mec1, c.cli, c.admin):
        assert c.req('get', '/api/auditoria', uid).status_code == 403
    assert c.gw.client.get('/api/auditoria').status_code == 401
