"""Auth-service: papéis do negócio (admin/dono/mecanico/cliente) e vínculo com a oficina."""
from __future__ import annotations

import os

import pytest

TOKEN = {'X-Internal-Token': os.environ['INTERNAL_TOKEN']}


def _registrar(c, email='dono@oficinaos.example'):
    return c.post('/register', json={'nome': 'Dono Teste', 'email': email, 'senha': 'segredo123'})


def test_cadastro_publico_ignora_papel_enviado(auth_client):
    r = auth_client.post('/register', json={
        'nome': 'Intruso', 'email': 'x@oficinaos.example', 'senha': 'segredo123',
        'role': 'admin', 'oficina_id': 99,
    })
    assert r.status_code == 201
    user = r.get_json()['user']
    assert user['role'] == 'dono'
    assert user['oficina_id'] is None


def test_me_devolve_papel_e_oficina(auth_client):
    _registrar(auth_client)
    user = auth_client.get('/me').get_json()['user']
    assert user['role'] == 'dono'
    assert 'oficina_id' in user


def test_internal_register_exige_token(auth_client):
    r = auth_client.post('/internal/register', json={})
    assert r.status_code == 403


@pytest.mark.parametrize('role', ['admin', 'superuser', '', 'usuario'])
def test_internal_register_papel_invalido_400(auth_client, role):
    r = auth_client.post('/internal/register', headers=TOKEN, json={
        'nome': 'Fulano', 'email': 'f@oficinaos.example', 'senha': 'segredo123', 'role': role, 'oficina_id': 1})
    assert r.status_code == 400


def test_internal_register_cria_mecanico_na_oficina(auth_client):
    r = auth_client.post('/internal/register', headers=TOKEN, json={
        'nome': 'Mecânico', 'email': 'm@oficinaos.example', 'senha': 'segredo123', 'role': 'mecanico', 'oficina_id': 7})
    assert r.status_code == 201
    assert r.get_json()['user']['role'] == 'mecanico'
    assert r.get_json()['user']['oficina_id'] == 7
    assert auth_client.get('/me').get_json()['user']['oficina_id'] == 7


def test_internal_register_exige_oficina(auth_client):
    r = auth_client.post('/internal/register', headers=TOKEN, json={
        'nome': 'Mecânico', 'email': 'm@oficinaos.example', 'senha': 'segredo123', 'role': 'mecanico'})
    assert r.status_code == 400


def test_vincular_oficina_so_para_dono_sem_oficina(auth_client):
    uid = _registrar(auth_client).get_json()['user']['id']
    r = auth_client.post(f'/internal/users/{uid}/oficina', headers=TOKEN, json={'oficina_id': 3})
    assert r.status_code == 200 and r.get_json()['user']['oficina_id'] == 3
    r2 = auth_client.post(f'/internal/users/{uid}/oficina', headers=TOKEN, json={'oficina_id': 4})
    assert r2.status_code == 409


def test_equipe_da_oficina_lista_so_a_propria(auth_client):
    for i, (role, of) in enumerate([('mecanico', 1), ('cliente', 1), ('mecanico', 2)]):
        auth_client.post('/internal/register', headers=TOKEN, json={
            'nome': f'U{i}', 'email': f'u{i}@oficinaos.example', 'senha': 'segredo123', 'role': role, 'oficina_id': of})
    r = auth_client.get('/internal/oficinas/1/usuarios', headers=TOKEN)
    assert r.status_code == 200
    emails = {u['email'] for u in r.get_json()['usuarios']}
    assert emails == {'u0@oficinaos.example', 'u1@oficinaos.example'}
    assert all('senha_hash' not in u for u in r.get_json()['usuarios'])


def test_admin_troca_papel_com_validacao(auth_client, monkeypatch):
    from auth_service import app as auth_app
    from auth_service.models import User
    from werkzeug.security import generate_password_hash
    with auth_app.session_scope() as db:
        db.add(User(nome='Adm', email='adm@oficinaos.example', senha_hash=generate_password_hash('segredo123'), role='admin'))
    alvo = _registrar(auth_client, 'alvo@oficinaos.example').get_json()['user']['id']
    auth_client.post('/logout')
    assert auth_client.post('/login', json={'email': 'adm@oficinaos.example', 'senha': 'segredo123'}).status_code == 200
    assert auth_client.post(f'/admin/users/{alvo}/role', json={'role': 'chefe'}).status_code == 400
    r = auth_client.post(f'/admin/users/{alvo}/role', json={'role': 'mecanico'})
    assert r.status_code == 200 and r.get_json()['user']['role'] == 'mecanico'


def test_dono_nao_troca_papel_de_ninguem(auth_client):
    uid = _registrar(auth_client).get_json()['user']['id']
    assert auth_client.post(f'/admin/users/{uid}/role', json={'role': 'admin'}).status_code == 403
