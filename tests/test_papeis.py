"""Gateway: autorização por papel, cadastro orquestrado e isolamento por oficina (clientes e veículos)."""
from __future__ import annotations

from backend.models import Oficina


def _oficina(gw, nome='Oficina A', codigo='CODIGO-A'):
    with gw.scope() as db:
        o = Oficina(nome=nome, codigo_convite=codigo)
        db.add(o)
        db.flush()
        return o.id


def _h(gw, uid):
    return {'headers': {'X-Test-User': str(uid)}}


# --- 401 / 403 / 409 -------------------------------------------------------

def test_sem_login_401(gw):
    assert gw.client.get('/api/clientes').status_code == 401
    assert gw.client.post('/api/clientes', json={'nome': 'X'}).status_code == 401


def test_mecanico_criando_cliente_403_chamando_a_api_direto(gw):
    of = _oficina(gw)
    mec = gw.auth.add('mecanico', of)
    r = gw.client.post('/api/clientes', json={'nome': 'Fulano'}, **_h(gw, mec))
    assert r.status_code == 403
    assert any(e['acao'] == 'acesso_negado' and e['usuario_id'] == mec for e in gw.eventos)


def test_cliente_nao_lista_clientes_e_admin_nao_opera_oficina(gw):
    of = _oficina(gw)
    cli = gw.auth.add('cliente', of)
    adm = gw.auth.add('admin', None)
    assert gw.client.get('/api/clientes', **_h(gw, cli)).status_code == 403
    assert gw.client.get('/api/clientes', **_h(gw, adm)).status_code == 403


def test_dono_sem_oficina_recebe_409_com_codigo(gw):
    dono = gw.auth.add('dono', None)
    r = gw.client.get('/api/clientes', **_h(gw, dono))
    assert r.status_code == 409 and r.get_json()['codigo'] == 'sem_oficina'


def test_onboarding_dono_sem_oficina_cria_oficina(gw):
    dono = gw.auth.add('dono', None)
    r = gw.client.post('/api/oficinas', json={'nome': 'Minha Oficina'}, **_h(gw, dono))
    assert r.status_code == 201
    assert gw.auth.users[dono]['oficina_id'] == r.get_json()['oficina']['id']
    assert any(e['acao'] == 'oficina.criada' for e in gw.eventos)
    # segunda tentativa: já tem oficina
    assert gw.client.post('/api/oficinas', json={'nome': 'Outra'}, **_h(gw, dono)).status_code == 403


# --- cadastro orquestrado --------------------------------------------------

def test_cadastro_dono_cria_oficina_e_usuario(gw):
    r = gw.client.post('/api/cadastro', json={'tipo': 'dono', 'nome': 'Joana', 'email': 'joana@oficinaos.example',
                                              'senha': 'segredo123', 'nome_oficina': 'Auto Joana'})
    assert r.status_code == 201
    user = r.get_json()['user']
    assert user['role'] == 'dono' and user['oficina_id']
    with gw.scope() as db:
        assert db.get(Oficina, user['oficina_id']).nome == 'Auto Joana'


def test_cadastro_dono_desfaz_oficina_se_auth_recusa(gw):
    gw.auth.add('dono', None, email='dup@oficinaos.example')
    r = gw.client.post('/api/cadastro', json={'tipo': 'dono', 'nome': 'Dup', 'email': 'dup@oficinaos.example',
                                              'senha': 'segredo123', 'nome_oficina': 'Fantasma'})
    assert r.status_code == 409
    with gw.scope() as db:
        assert db.query(Oficina).count() == 0


def test_cadastro_nao_aceita_papel_admin(gw):
    r = gw.client.post('/api/cadastro', json={'tipo': 'admin', 'nome': 'Evil', 'email': 'e@oficinaos.example',
                                              'senha': 'segredo123', 'nome_oficina': 'X'})
    assert r.status_code == 400


def test_cadastro_com_codigo_invalido_400(gw):
    r = gw.client.post('/api/cadastro', json={'tipo': 'mecanico', 'nome': 'Mec', 'email': 'm@oficinaos.example',
                                              'senha': 'segredo123', 'codigo_convite': 'NAO-EXISTE'})
    assert r.status_code == 400


def test_cadastro_mecanico_e_cliente_por_convite(gw):
    of = _oficina(gw, codigo='OF-TESTE123')
    r = gw.client.post('/api/cadastro', json={'tipo': 'mecanico', 'nome': 'Mec', 'email': 'm@oficinaos.example',
                                              'senha': 'segredo123', 'codigo_convite': ' of-teste123 '})
    assert r.status_code == 201 and r.get_json()['user']['oficina_id'] == of
    r2 = gw.client.post('/api/cadastro', json={'tipo': 'cliente', 'nome': 'Cli', 'email': 'c@oficinaos.example',
                                               'senha': 'segredo123', 'codigo_convite': 'OF-TESTE123'})
    assert r2.status_code == 201
    assert sum(1 for e in gw.eventos if e['acao'] == 'membro.entrou') == 2


def test_segundo_mecanico_no_free_recebe_402(gw):
    _oficina(gw, codigo='OF-LIMITE01')
    corpo = {'tipo': 'mecanico', 'senha': 'segredo123', 'codigo_convite': 'OF-LIMITE01'}
    assert gw.client.post('/api/cadastro', json={**corpo, 'nome': 'M1', 'email': 'm1@oficinaos.example'}).status_code == 201
    r = gw.client.post('/api/cadastro', json={**corpo, 'nome': 'M2', 'email': 'm2@oficinaos.example'})
    assert r.status_code == 402
    body = r.get_json()
    assert body['codigo'] == 'limite_plano' and body['limite'] == 1 and body['uso'] == 1 and body['plano'] == 'free'
    assert 'Pro' in body['como_liberar']
    assert any(e['acao'] == 'plano.limite_atingido' for e in gw.eventos)


def test_cliente_que_entra_assume_cadastro_feito_pelo_dono(gw):
    of = _oficina(gw, codigo='OF-LINK0001')
    with gw.scope() as db:
        from backend.models import Cliente
        db.add(Cliente(oficina_id=of, nome='Carlos', email='carlos@oficinaos.example'))
    gw.client.post('/api/cadastro', json={'tipo': 'cliente', 'nome': 'Carlos', 'email': 'CARLOS@oficinaos.example',
                                          'senha': 'segredo123', 'codigo_convite': 'OF-LINK0001'})
    with gw.scope() as db:
        from backend.models import Cliente
        clientes = db.query(Cliente).all()
        assert len(clientes) == 1 and clientes[0].usuario_id is not None


# --- clientes e veículos: CRUD e isolamento --------------------------------

def _dono(gw, codigo='CODIGO-A'):
    of = _oficina(gw, codigo=codigo, nome=f'Of {codigo}')
    return of, gw.auth.add('dono', of)


def test_crud_de_clientes(gw):
    of, dono = _dono(gw)
    h = _h(gw, dono)
    r = gw.client.post('/api/clientes', json={'nome': 'Carlos', 'telefone': '14 99999-0001'}, **h)
    assert r.status_code == 201
    cid = r.get_json()['cliente']['id']
    assert gw.client.get(f'/api/clientes/{cid}', **h).status_code == 200
    assert gw.client.put(f'/api/clientes/{cid}', json={'nome': 'Carlos P.'}, **h).get_json()['cliente']['nome'] == 'Carlos P.'
    assert len(gw.client.get('/api/clientes', **h).get_json()['clientes']) == 1
    assert gw.client.delete(f'/api/clientes/{cid}', **h).status_code == 200
    assert gw.client.get(f'/api/clientes/{cid}', **h).status_code == 404
    assert any(e['acao'] == 'cliente.criado' for e in gw.eventos)


def test_cliente_de_outra_oficina_404(gw):
    _, dono_a = _dono(gw, 'A')
    _, dono_b = _dono(gw, 'B')
    cid = gw.client.post('/api/clientes', json={'nome': 'Da A'}, **_h(gw, dono_a)).get_json()['cliente']['id']
    for metodo, kw in (('get', {}), ('put', {'json': {'nome': 'Hack'}}), ('delete', {})):
        r = getattr(gw.client, metodo)(f'/api/clientes/{cid}', **_h(gw, dono_b), **kw)
        assert r.status_code == 404, metodo
    assert gw.client.get('/api/clientes', **_h(gw, dono_b)).get_json()['clientes'] == []
    assert any(e['acao'] == 'acesso_negado' and e['usuario_id'] == dono_b for e in gw.eventos)


def test_oficina_id_do_corpo_e_ignorado(gw):
    of_a, dono_a = _dono(gw, 'A')
    of_b, _ = _dono(gw, 'B')
    r = gw.client.post('/api/clientes', json={'nome': 'Tentativa', 'oficina_id': of_b}, **_h(gw, dono_a))
    cid = r.get_json()['cliente']['id']
    with gw.scope() as db:
        from backend.models import Cliente
        assert db.get(Cliente, cid).oficina_id == of_a


def test_veiculos_placa_unica_por_oficina_e_normalizada(gw):
    of, dono = _dono(gw)
    h = _h(gw, dono)
    cid = gw.client.post('/api/clientes', json={'nome': 'Cli'}, **h).get_json()['cliente']['id']
    r = gw.client.post('/api/veiculos', json={'cliente_id': cid, 'placa': 'abc-1d23', 'marca': 'Fiat', 'modelo': 'Uno',
                                              'ano': 2014}, **h)
    assert r.status_code == 201 and r.get_json()['veiculo']['placa'] == 'ABC1D23'
    dup = gw.client.post('/api/veiculos', json={'cliente_id': cid, 'placa': 'ABC1D23', 'marca': 'X', 'modelo': 'Y'}, **h)
    assert dup.status_code == 409
    assert gw.client.post('/api/veiculos', json={'cliente_id': cid, 'placa': '123', 'marca': 'X', 'modelo': 'Y'},
                          **h).status_code == 400


def test_mesma_placa_em_oficinas_diferentes_pode(gw):
    _, dono_a = _dono(gw, 'A')
    _, dono_b = _dono(gw, 'B')
    for dono in (dono_a, dono_b):
        h = _h(gw, dono)
        cid = gw.client.post('/api/clientes', json={'nome': 'Cli'}, **h).get_json()['cliente']['id']
        r = gw.client.post('/api/veiculos', json={'cliente_id': cid, 'placa': 'AAA1A11', 'marca': 'M', 'modelo': 'X'}, **h)
        assert r.status_code == 201


def test_veiculo_com_cliente_de_outra_oficina_404(gw):
    _, dono_a = _dono(gw, 'A')
    _, dono_b = _dono(gw, 'B')
    cid_b = gw.client.post('/api/clientes', json={'nome': 'Da B'}, **_h(gw, dono_b)).get_json()['cliente']['id']
    r = gw.client.post('/api/veiculos', json={'cliente_id': cid_b, 'placa': 'AAA1A11', 'marca': 'M', 'modelo': 'X'},
                       **_h(gw, dono_a))
    assert r.status_code == 404


def test_cliente_logado_so_ve_os_proprios_veiculos(gw):
    of, dono = _dono(gw)
    h = _h(gw, dono)
    cli_user = gw.auth.add('cliente', of, nome='Marina')
    with gw.scope() as db:
        from backend.models import Cliente
        db.add(Cliente(oficina_id=of, usuario_id=cli_user, nome='Marina'))
    meu = gw.client.post('/api/clientes', json={'nome': 'Outro'}, **h).get_json()['cliente']['id']
    gw.client.post('/api/veiculos', json={'cliente_id': meu, 'placa': 'OUT1R01', 'marca': 'M', 'modelo': 'X'}, **h)
    with gw.scope() as db:
        from backend.models import Cliente
        marina = db.query(Cliente).filter_by(usuario_id=cli_user).one().id
    v = gw.client.post('/api/veiculos', json={'cliente_id': marina, 'placa': 'MAR1N01', 'marca': 'M', 'modelo': 'Y'},
                       **h).get_json()['veiculo']['id']
    lista = gw.client.get('/api/veiculos', **_h(gw, cli_user)).get_json()['veiculos']
    assert [x['placa'] for x in lista] == ['MAR1N01']
    outro_id = next(x['id'] for x in gw.client.get('/api/veiculos', **h).get_json()['veiculos'] if x['placa'] == 'OUT1R01')
    assert gw.client.get(f'/api/veiculos/{outro_id}', **_h(gw, cli_user)).status_code == 404
    assert gw.client.get(f'/api/veiculos/{v}', **_h(gw, cli_user)).status_code == 200
    assert gw.client.post('/api/veiculos', json={'cliente_id': marina, 'placa': 'XXX1X11', 'marca': 'M', 'modelo': 'Y'},
                          **_h(gw, cli_user)).status_code == 403


def test_auth_fora_do_ar_503(gw):
    gw.auth.indisponivel = True
    assert gw.client.get('/api/clientes', headers={'X-Test-User': '1'}).status_code == 503
