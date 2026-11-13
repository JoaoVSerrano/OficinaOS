#!/usr/bin/env python3
"""Prints da A10 e A11 que dá para tirar numa stack LOCAL (landing, foto da OS, 403/404 no Swagger, auditoria, limite do Free, painel admin).

Uso:
    ADMIN_EMAIL=... ADMIN_PASSWORD=... python scripts/evidencias/local.py --base-url http://localhost:8090

Regras (CLAUDE.md): contas de demonstração @oficinaos.example criadas pela própria API; senhas só em variável de
ambiente (a do admin) ou a SENHA_DEMO dos cenários; janela 1440x900, sem editar a imagem; nunca captura variáveis,
chaves ou tokens. Os prints vêm do ambiente local: a legenda no relatório diz isso.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

RAIZ = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(RAIZ / 'scripts' / 'cenarios'))
from _comum import DOMINIO_CONTAS, SENHA_DEMO, chamar, sessao, sufixo  # noqa: E402

SAIDA = RAIZ / 'docs' / 'p2' / 'prints'
OPCOES = dict(viewport={'width': 1440, 'height': 900}, device_scale_factor=1.5, locale='pt-BR', timezone_id='America/Sao_Paulo',
              color_scheme='light')
TEMA_CLARO = "try{localStorage.setItem('oficinaos.tema','claro')}catch(e){}"


def cadastrar(base: str, tipo: str, nome: str, email: str, **extra):
    s = sessao(base)
    r = chamar(s, 'POST', '/api/cadastro', json={'tipo': tipo, 'nome': nome, 'email': email, 'senha': SENHA_DEMO, **extra})
    assert r.status_code == 201, r.text
    return s, r.json()['user']


def foto_de_teste(pw_ctx) -> bytes:
    """Imagem de teste (não é foto de cliente): um quadro simples gerado no próprio navegador."""
    pg = pw_ctx.new_page()
    pg.set_viewport_size({'width': 640, 'height': 480})
    pg.set_content('<body style="margin:0;display:grid;place-items:center;height:100vh;background:linear-gradient(135deg,#334155,#64748b);'
                   'font:600 28px sans-serif;color:#fff">Foto de teste — painel do veículo</body>')
    png = pg.screenshot(type='png')
    pg.close()
    return png


def swagger_executar(pg: Page, base: str, caminho: str, metodo: str, parametro: str, valor: str, arquivo: str) -> None:
    pg.goto(base + '/docs')
    pg.wait_for_selector('.opblock-summary-path', timeout=30000)
    pg.fill('input.download-url-input', '') if False else None
    bloco = pg.locator(f'.opblock-{metodo}').filter(has=pg.locator(f'[data-path="{caminho}"]')).first
    bloco.locator('.opblock-summary').click()
    bloco.get_by_role('button', name='Try it out').click()
    bloco.get_by_placeholder(parametro).fill(valor)
    bloco.get_by_role('button', name='Execute').click()
    bloco.locator('.responses-table.live-responses-table .response-col_status').first.wait_for(timeout=30000)
    bloco.scroll_into_view_if_needed()
    pg.wait_for_timeout(500)
    pg.screenshot(path=str(SAIDA / arquivo))
    print('ok', arquivo)


def executar(base: str) -> None:
    sfx = sufixo()
    SAIDA.mkdir(parents=True, exist_ok=True)
    # oficina A (dono, mecânico, cliente, veículo, OS) e oficina B (dono)
    dono, _ = cadastrar(base, 'dono', 'Dono Evidência', f'ev{sfx}{DOMINIO_CONTAS}', nome_oficina=f'Oficina Evidência {sfx}')
    cod = chamar(dono, 'GET', '/api/oficina').json()['oficina']['codigo_convite']
    mec, mu = cadastrar(base, 'mecanico', 'Mecânico Evidência', f'evm{sfx}{DOMINIO_CONTAS}', codigo_convite=cod)
    cadastrar(base, 'cliente', 'Cliente Evidência', f'evc{sfx}{DOMINIO_CONTAS}', codigo_convite=cod)
    cli = next(c for c in chamar(dono, 'GET', '/api/clientes').json()['clientes'] if c['nome'] == 'Cliente Evidência')
    vei = chamar(dono, 'POST', '/api/veiculos', json={'cliente_id': cli['id'], 'placa': f'EV{sfx[-5:]}', 'marca': 'Fiat', 'modelo': 'Strada',
                                                       'ano': 2019}).json()['veiculo']['id']
    os_id = chamar(dono, 'POST', '/api/os', json={'veiculo_id': vei, 'descricao': 'Painel acendendo luz da injeção', 'km_entrada': 61800,
                                                  'mecanico_id': mu['id']}).json()['ordem']['id']
    outro, _ = cadastrar(base, 'dono', 'Dono Outra Oficina', f'evo{sfx}{DOMINIO_CONTAS}', nome_oficina=f'Outra Oficina {sfx}')
    # oficina Free para o limite (20 OS/mês)
    free, _ = cadastrar(base, 'dono', 'Dono Free', f'evf{sfx}{DOMINIO_CONTAS}', nome_oficina=f'Oficina Free {sfx}')
    c2 = chamar(free, 'POST', '/api/clientes', json={'nome': 'Cliente Free', 'telefone': '(14) 99999-0000'}).json()['cliente']['id']
    v2 = chamar(free, 'POST', '/api/veiculos', json={'cliente_id': c2, 'placa': f'FR{sfx[-5:]}', 'marca': 'VW', 'modelo': 'Gol', 'ano': 2015}).json()['veiculo']['id']
    for i in range(20):
        r = chamar(free, 'POST', '/api/os', json={'veiculo_id': v2, 'descricao': f'Serviço de rotina {i + 1}'})
        assert r.status_code == 201, r.text

    def entrar_via_api(ctx, email: str, senha: str = SENHA_DEMO) -> None:
        r = ctx.request.post(base + '/api/auth/login', data={'email': email, 'senha': senha})
        assert r.ok, f'login falhou ({r.status})'

    with sync_playwright() as p:
        nav = p.chromium.launch()

        def contexto():
            c = nav.new_context(**OPCOES)
            c.add_init_script(TEMA_CLARO)
            return c

        # A10 — landing (sem login)
        c = contexto(); pg = c.new_page(); pg.goto(base + '/'); pg.wait_for_load_state('networkidle'); pg.wait_for_timeout(400)
        pg.screenshot(path=str(SAIDA / 'a10-01-landing.png')); c.close(); print('ok a10-01')

        # A10 — foto na OS (dono) + 403/404 no Swagger + auditoria
        c = contexto(); entrar_via_api(c, f'ev{sfx}{DOMINIO_CONTAS}')
        png = foto_de_teste(c)
        r = c.request.post(f'{base}/api/os/{os_id}/anexos', multipart={'arquivo': {'name': 'painel.png', 'mimeType': 'image/png', 'buffer': png}})
        assert r.status == 201, r.text()
        pg = c.new_page(); pg.goto(f'{base}/app/os/{os_id}'); pg.wait_for_load_state('networkidle')
        pg.locator('.thumbs').first.scroll_into_view_if_needed(); pg.evaluate('window.scrollBy(0, 200)')
        pg.wait_for_timeout(600)
        pg.screenshot(path=str(SAIDA / 'a10-03-detalhe-os-foto.png')); print('ok a10-03')
        pg.goto(base + '/app/auditoria'); pg.wait_for_load_state('networkidle'); pg.wait_for_timeout(600)
        pg.screenshot(path=str(SAIDA / 'a10-06-log-eventos.png')); print('ok a10-06')
        c.close()

        c = contexto(); entrar_via_api(c, f'evm{sfx}{DOMINIO_CONTAS}'); pg = c.new_page()
        swagger_executar(pg, base, '/api/os/{os_id}', 'delete', 'os_id', str(os_id), 'a10-04-403-papel.png'); c.close()
        c = contexto(); entrar_via_api(c, f'evo{sfx}{DOMINIO_CONTAS}'); pg = c.new_page()
        swagger_executar(pg, base, '/api/os/{os_id}', 'get', 'os_id', str(os_id), 'a10-05-bloqueio-outro.png'); c.close()

        # A11 — 21ª OS recusada no Free
        c = contexto(); entrar_via_api(c, f'evf{sfx}{DOMINIO_CONTAS}'); pg = c.new_page()
        pg.goto(base + '/app/os/nova'); pg.wait_for_load_state('networkidle')
        pg.get_by_label('Veículo', exact=True).select_option(index=1)
        pg.get_by_label('Problema ou serviço a fazer').fill('Troca de pastilhas de freio')
        pg.get_by_role('button', name='Abrir ordem de serviço').click()
        pg.locator('.alert.err').wait_for(timeout=15000); pg.wait_for_timeout(400)
        pg.screenshot(path=str(SAIDA / 'a11-01-limite-free.png')); c.close(); print('ok a11-01')

        # A11 — painel admin (credenciais só por variável de ambiente)
        if os.getenv('ADMIN_EMAIL') and os.getenv('ADMIN_PASSWORD'):
            c = contexto(); entrar_via_api(c, os.environ['ADMIN_EMAIL'], os.environ['ADMIN_PASSWORD']); pg = c.new_page()
            pg.goto(base + '/app/admin'); pg.wait_for_load_state('networkidle'); pg.wait_for_timeout(800)
            pg.screenshot(path=str(SAIDA / 'a11-06-painel-admin.png')); c.close(); print('ok a11-06')
        nav.close()


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--base-url', required=True)
    executar(ap.parse_args().base_url.rstrip('/'))
