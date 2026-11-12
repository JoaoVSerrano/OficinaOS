#!/usr/bin/env python3
"""Cenário de aceite da Atividade 10 (roteiro do professor), com requests.

Uso:  python scripts/cenarios/ativ10.py --base-url http://localhost:8090 \
          [--admin-email admin@oficinaos.example --admin-password ...]
Sem credenciais de admin, o passo 6 (eventos no log) é pulado.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _comum import (DOMINIO_CONTAS, SENHA_DEMO, Relatorio, baixar_bundles, chamar, main_seguro, png_minimo, sessao,
                    sufixo)


def cadastrar(base, tipo, nome, email, **extra):
    s = sessao(base)
    r = chamar(s, 'POST', '/api/cadastro', json={'tipo': tipo, 'nome': nome, 'email': email, 'senha': SENHA_DEMO, **extra})
    return s, r


def executar(base: str, admin_email: str | None, admin_senha: str | None) -> int:
    rel = Relatorio()
    sfx = sufixo()
    anon = sessao(base)

    # 1. abre o subdomínio sem login e vê a landing
    index, bundles = baixar_bundles(anon)
    rel.passo('1. Página inicial abre sem login (app Angular carregado)', '<app-root' in index)
    rel.passo('1. Landing tem a proposta de valor e o botão "Criar conta grátis"',
              'Pare de perder serviço no caderno' in bundles and 'Criar conta grátis' in bundles)
    rel.passo('1. /api/auth/me sem login não é erro (sessão vazia)', chamar(anon, 'GET', '/api/auth/me').json().get('user') is None)

    # 2. cria duas contas de papéis diferentes (dono + mecânico por convite) e uma segunda oficina
    dono, r = cadastrar(base, 'dono', 'Dona Demo', f'dono{sfx}{DOMINIO_CONTAS}', nome_oficina=f'Oficina Demo {sfx}')
    rel.passo('2. Dono cria conta e oficina', r.status_code == 201 and r.json()['user']['role'] == 'dono', r.text[:120])
    codigo = chamar(dono, 'GET', '/api/oficina').json()['oficina'].get('codigo_convite', '')
    rel.passo('2. Dono vê o código de convite', codigo.startswith('OF-'))
    mec, r = cadastrar(base, 'mecanico', 'Mecânico Demo', f'mec{sfx}{DOMINIO_CONTAS}', codigo_convite=codigo)
    rel.passo('2. Mecânico cria conta pelo código de convite', r.status_code == 201 and r.json()['user']['role'] == 'mecanico', r.text[:120])
    mec_id = r.json()['user']['id'] if r.status_code == 201 else None
    _, r = cadastrar(base, 'mecanico', 'Mecânico 2', f'mec2{sfx}{DOMINIO_CONTAS}', codigo_convite='CODIGO-INVALIDO')
    rel.passo('2. Código de convite inválido é recusado (400)', r.status_code == 400)
    outro, r = cadastrar(base, 'dono', 'Outro Dono', f'outro{sfx}{DOMINIO_CONTAS}', nome_oficina=f'Concorrente {sfx}')
    rel.passo('2. Segunda oficina (outro dono) criada', r.status_code == 201)

    # 3. com a 1ª conta: cria, edita e apaga registros, com upload
    r = chamar(dono, 'POST', '/api/clientes', json={'nome': 'Carlos Pereira', 'telefone': '14 99999-0001'})
    cli = r.json().get('cliente', {}).get('id')
    rel.passo('3. Cria cliente', r.status_code == 201)
    r = chamar(dono, 'POST', '/api/veiculos', json={'cliente_id': cli, 'placa': f'T{sfx[-6:]}', 'marca': 'Fiat', 'modelo': 'Uno', 'ano': 2014})
    vei = r.json().get('veiculo', {}).get('id')
    rel.passo('3. Cria veículo', r.status_code == 201, r.text[:120])
    r = chamar(dono, 'POST', '/api/os', json={'veiculo_id': vei, 'descricao': 'Barulho na suspensão dianteira', 'mecanico_id': mec_id})
    os_id = r.json().get('ordem', {}).get('id')
    rel.passo('3. Abre ordem de serviço', r.status_code == 201, r.text[:120])
    r = chamar(dono, 'PUT', f'/api/os/{os_id}', json={'descricao': 'Troca de pastilhas e disco de freio'})
    rel.passo('3. Edita a ordem de serviço', r.status_code == 200 and 'pastilhas' in r.json()['ordem']['descricao'])
    r = chamar(dono, 'POST', f'/api/os/{os_id}/itens', json={'tipo': 'peca', 'descricao': 'Pastilha de freio', 'quantidade': 2, 'valor_unitario_centavos': 11000})
    rel.passo('3. Adiciona item e o total vira a soma', r.status_code == 201 and r.json()['ordem']['valor_total_centavos'] == 22000)
    r = chamar(dono, 'POST', f'/api/os/{os_id}/anexos', files={'arquivo': ('entrada.png', png_minimo(), 'image/png')})
    anexo = r.json().get('anexo', {})
    rel.passo('3. Envia foto da OS (upload no MinIO)', r.status_code == 201, r.text[:160])
    r = chamar(dono, 'GET', anexo.get('url', '/nada'))
    rel.passo('3. Foto volta pela rota protegida do gateway', r.status_code == 200 and r.headers.get('Content-Type') == 'image/png')
    r = chamar(anon, 'GET', anexo.get('url', '/nada'))
    rel.passo('3. Sem login a foto NÃO é entregue', r.status_code == 401)
    descartavel = chamar(dono, 'POST', '/api/os', json={'veiculo_id': vei, 'descricao': 'Ordem para apagar'}).json()['ordem']['id']
    r = chamar(dono, 'DELETE', f'/api/os/{descartavel}')
    rel.passo('3. Apaga uma ordem de serviço (exclusão lógica)', r.status_code == 200)
    rel.passo('3. A OS apagada some da lista', all(o['id'] != descartavel for o in chamar(dono, 'GET', '/api/os').json()['ordens']))

    # 4. com a 2ª oficina: troca o ID na URL ou chama a API e recebe 404
    for metodo, caminho, corpo in (('GET', f'/api/os/{os_id}', None), ('PUT', f'/api/os/{os_id}', {'descricao': 'invadindo'}),
                                   ('DELETE', f'/api/os/{os_id}', None), ('GET', anexo.get('url', '/x'), None)):
        r = chamar(outro, metodo, caminho, json=corpo) if corpo else chamar(outro, metodo, caminho)
        rel.passo(f'4. Outra oficina: {metodo} {caminho.split("?")[0]} -> 404', r.status_code == 404, f'recebeu {r.status_code}')
    rel.passo('4. Lista da outra oficina não mostra nada da primeira', chamar(outro, 'GET', '/api/os').json()['ordens'] == [])

    # 5. ação proibida ao papel direto na API -> 403
    r = chamar(mec, 'DELETE', f'/api/os/{os_id}')
    rel.passo('5. Mecânico tentando excluir OS -> 403', r.status_code == 403, f'recebeu {r.status_code}')
    r = chamar(mec, 'POST', '/api/clientes', json={'nome': 'Intruso'})
    rel.passo('5. Mecânico tentando criar cliente -> 403', r.status_code == 403)
    r = chamar(mec, 'GET', '/api/equipe')
    rel.passo('5. Mecânico tentando ver a equipe -> 403', r.status_code == 403)
    r = chamar(anon, 'GET', '/api/os')
    rel.passo('5. Sem login -> 401', r.status_code == 401)

    # 6. como admin, vê no log os eventos com quem e quando
    if admin_email and admin_senha:
        adm = sessao(base)
        r = chamar(adm, 'POST', '/api/auth/login', json={'email': admin_email, 'senha': admin_senha})
        rel.passo('6. Admin entra', r.status_code == 200, f'recebeu {r.status_code}')
        user = chamar(dono, 'GET', '/api/auth/me').json()['user']
        logs = chamar(adm, 'GET', '/api/admin/logs', params={'oficina_id': user['oficina_id'], 'n': 200}).json().get('logs', [])
        acoes = {e['acao'] for e in logs}
        rel.passo('6. Log tem os eventos de negócio da oficina', {'os.aberta', 'os.editada', 'os.excluida', 'anexo.enviado', 'cliente.criado'} <= acoes, str(sorted(acoes)))
        rel.passo('6. Cada evento diz quem (usuário e papel) e quando', all(e.get('usuario_id') and e.get('papel') and e.get('ts_ms') for e in logs if e['acao'].startswith('os.')))
        todos = chamar(adm, 'GET', '/api/admin/logs', params={'acao': 'acesso_negado', 'n': 200}).json().get('logs', [])
        rel.passo('6. Acessos negados (403/404) aparecem no log', len(todos) >= 1)
        rel.passo('6. Dono NÃO acessa o log de todas as oficinas', chamar(dono, 'GET', '/api/admin/logs').status_code == 403)
        r = chamar(dono, 'GET', '/api/auditoria')
        rel.passo('6. Dono vê a auditoria só da própria oficina', r.status_code == 200 and all(e.get('oficina_id') == str(user['oficina_id']) for e in r.json()['logs']))
    else:
        rel.pular('6. Eventos no log como admin', 'informe --admin-email e --admin-password')

    # 7. procura Tom Hanks / filme / TMDB nas telas e rotas
    rel.passo('7. Nenhuma menção a Tom Hanks, filme ou TMDB nas telas', not __import__('re').search(r'tom ?hanks|tmdb|filme', index + bundles, __import__('re').I))
    rel.passo('7. Rotas do catálogo antigo não existem (404)', all(chamar(anon, 'GET', c).status_code == 404 for c in ('/api/catalog', '/api/favorites', '/api/comments')))
    return rel.concluir()


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base-url', required=True)
    ap.add_argument('--admin-email', default=os.getenv('ADMIN_EMAIL'))
    ap.add_argument('--admin-password', default=os.getenv('ADMIN_PASSWORD'))
    a = ap.parse_args()
    main_seguro(lambda: executar(a.base_url, a.admin_email, a.admin_password))
