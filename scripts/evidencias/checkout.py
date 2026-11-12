#!/usr/bin/env python3
"""Prints da Atividade 11 com um navegador real (Playwright): limite do Free, checkout 4242, Pro, portal, Free e painel.

Uso:
    ADMIN_EMAIL=... ADMIN_PASSWORD=... python scripts/evidencias/checkout.py --base-url https://<subdominio>

Regras (docs/execucao/EXECUCAO.md, seção 9):
  * Stripe SOMENTE em modo de teste: o script confere a faixa "modo de teste" na página da Stripe ANTES de digitar o
    cartão e aborta se ela não aparecer. O cartão 4242 é o cartão de teste público da Stripe.
  * Contas de demonstração @oficinaos.example criadas pela própria API; senhas só em variável de ambiente.
  * Print do tamanho da janela (1440x900), sem desenhar nada na imagem. Nunca captura variáveis, chaves ou tokens.
  * Os prints "assistidos" (painel da Stripe, entregas do webhook) NÃO são feitos aqui: exigem o login do João.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from playwright.sync_api import Page, sync_playwright

RAIZ = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(RAIZ / 'scripts' / 'cenarios'))
from _comum import DOMINIO_CONTAS, SENHA_DEMO, sufixo  # noqa: E402

SAIDA = RAIZ / 'docs' / 'p2' / 'prints'
OPCOES = dict(viewport={'width': 1440, 'height': 900}, device_scale_factor=1.5, locale='pt-BR',
              timezone_id='America/Sao_Paulo')
CARTAO_TESTE = {'numero': '4242 4242 4242 4242', 'validade': '12 / 34', 'cvc': '123'}
capturas: list[dict] = []


def api(sess: requests.Session, base: str, metodo: str, caminho: str, **kw) -> requests.Response:
    return sess.request(metodo, base + caminho, timeout=30, **kw)


def cookies_para_navegador(sess: requests.Session, base: str) -> list[dict]:
    host = urlparse(base).hostname
    return [{'name': c.name, 'value': c.value, 'domain': host, 'path': '/', 'httpOnly': True,
             'secure': base.startswith('https')} for c in sess.cookies]


def tirar(page: Page, arquivo: str, legenda: str) -> None:
    """Salva o print e registra a data/hora REAIS da captura (vão na legenda do relatório)."""
    page.wait_for_timeout(800)
    SAIDA.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SAIDA / arquivo))
    agora = datetime.now().astimezone().strftime('%d/%m/%Y %H:%M:%S %z')
    capturas.append({'arquivo': arquivo, 'legenda': legenda, 'capturado_em': agora})
    print(f'[PRINT] {arquivo}  ({agora})')


def preparar_oficina(base: str) -> tuple[requests.Session, str]:
    """Cria dono + veículo + 20 OS pela API; a 21ª será tentada pela interface."""
    sfx = sufixo()
    s = requests.Session()
    r = api(s, base, 'POST', '/api/cadastro', json={'tipo': 'dono', 'nome': 'Dona Evidência', 'email': f'evid{sfx}{DOMINIO_CONTAS}',
                                                    'senha': SENHA_DEMO, 'nome_oficina': f'Oficina Evidência {sfx}'})
    r.raise_for_status()
    cli = api(s, base, 'POST', '/api/clientes', json={'nome': 'Carlos Evidência'}).json()['cliente']['id']
    api(s, base, 'POST', '/api/veiculos', json={'cliente_id': cli, 'placa': f'E{sfx[-6:]}', 'marca': 'Fiat', 'modelo': 'Uno', 'ano': 2014}).raise_for_status()
    vei = api(s, base, 'GET', '/api/veiculos').json()['veiculos'][0]['id']
    for i in range(20):
        api(s, base, 'POST', '/api/os', json={'veiculo_id': vei, 'descricao': f'Serviço de demonstração {i + 1}'}).raise_for_status()
    return s, sfx


def preencher_cartao(page: Page) -> None:
    """Checkout hospedado da Stripe: campos do cartão de teste público 4242."""
    def campo(rotulo: re.Pattern, seletor: str):
        loc = page.get_by_label(rotulo)
        return loc.first if loc.count() else page.locator(seletor).first
    campo(re.compile('n[úu]mero do cart|card number', re.I), '#cardNumber').fill(CARTAO_TESTE['numero'])
    campo(re.compile('validade|expiration', re.I), '#cardExpiry').fill(CARTAO_TESTE['validade'])
    campo(re.compile('cvc|seguran', re.I), '#cardCvc').fill(CARTAO_TESTE['cvc'])
    nome = page.locator('#billingName')
    if nome.count():
        nome.first.fill('Dona Evidência')
    pais = page.locator('#billingCountry')
    if pais.count() and pais.first.input_value() != 'BR':
        pais.first.select_option('BR')


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base-url', required=True)
    ap.add_argument('--visivel', action='store_true', help='abre o navegador com janela (para acompanhar ou assistir)')
    a = ap.parse_args()
    base = a.base_url.rstrip('/')
    admin_email, admin_senha = os.getenv('ADMIN_EMAIL'), os.getenv('ADMIN_PASSWORD')

    sess, _ = preparar_oficina(base)
    with sync_playwright() as p:
        nav = p.chromium.launch(headless=not a.visivel)
        ctx = nav.new_context(**OPCOES)
        ctx.add_cookies(cookies_para_navegador(sess, base))
        page = ctx.new_page()
        resultado = 0

        # a11-01: a 21ª OS é recusada com a mensagem do plano
        page.goto(f'{base}/app/os/nova', wait_until='networkidle')
        page.get_by_label('Veículo').select_option(index=1)
        page.get_by_label(re.compile('Problema ou serviço')).fill('A 21ª ordem do mês no plano Free')
        page.get_by_role('button', name=re.compile('Abrir ordem de serviço')).click()
        page.get_by_role('alert').filter(has_text=re.compile('Limite do plano')).wait_for(timeout=15000)
        tirar(page, 'a11-01-limite-free.png', '21ª OS recusada com a mensagem do plano Free')

        # a11-02: checkout da Stripe (modo de teste) com o cartão 4242
        page.goto(f'{base}/app/plano', wait_until='networkidle')
        page.get_by_role('button', name='Assinar Pro').click()
        try:
            page.wait_for_url(re.compile(r'https://checkout\.stripe\.com/'), timeout=30000)
        except Exception:
            print('[ERRO] o checkout não abriu a página da Stripe. A Stripe de TESTE está configurada no servidor '
                  '(STRIPE_SECRET_KEY, STRIPE_PRICE_ID)? Os prints já tirados foram mantidos.')
            nav.close()
            return 1
        page.wait_for_load_state('networkidle')
        if not page.get_by_text(re.compile('modo de teste|test mode', re.I)).first.is_visible():
            print('[ABORTADO] a página da Stripe não mostra a faixa de MODO DE TESTE. Nada foi digitado. '
                  'Confira se as chaves da stack são sk_test_/pk_test_.')
            nav.close()
            return 3
        preencher_cartao(page)
        tirar(page, 'a11-02-checkout-4242.png', 'Checkout da Stripe em modo de teste com o cartão 4242')
        page.get_by_role('button', name=re.compile('assinar|subscribe|pagar|pay', re.I)).last.click()

        # a11-03: de volta ao app, o plano só muda quando o webhook chega
        page.wait_for_url(re.compile(re.escape(base) + r'/app/plano\?assinatura=ok'), timeout=90000)
        page.get_by_role('heading', name=re.compile('Plano Pro')).wait_for(timeout=60000)
        tirar(page, 'a11-03-pro-ativo.png', 'App mostrando o plano Pro depois do webhook')

        # a11-06 / a11-07: portal (cancelamento imediato) e volta ao Free
        page.get_by_role('button', name='Gerenciar assinatura').click()
        page.wait_for_url(re.compile(r'https://billing\.stripe\.com/'), timeout=30000)
        page.wait_for_load_state('networkidle')
        try:
            page.get_by_text(re.compile('cancelar (o )?plano|cancel (plan|subscription)', re.I)).first.click()
            page.get_by_role('button', name=re.compile('cancelar (o )?plano|cancel (plan|subscription)', re.I)).last.click()
            page.get_by_text(re.compile('cancelad|canceled', re.I)).first.wait_for(timeout=20000)
            tirar(page, 'a11-06-portal-cancelar.png', 'Cancelamento imediato no portal do cliente')
            page.goto(f'{base}/app/plano', wait_until='networkidle')
            page.get_by_role('heading', name=re.compile('Plano Free')).wait_for(timeout=60000)
            tirar(page, 'a11-07-voltou-free.png', 'App de volta ao plano Free depois do webhook de cancelamento')
        except Exception as exc:
            print(f'[ASSISTIDO] o cancelamento no portal não pôde ser automatizado ({type(exc).__name__}). '
                  'Cancele pelo portal (aberto) e tire os prints a11-06 e a11-07 manualmente.')
            resultado = 1

        # a11-08: painel admin
        if admin_email and admin_senha:
            adm = requests.Session()
            api(adm, base, 'POST', '/api/auth/login', json={'email': admin_email, 'senha': admin_senha}).raise_for_status()
            ctx2 = nav.new_context(**OPCOES)
            ctx2.add_cookies(cookies_para_navegador(adm, base))
            pg = ctx2.new_page()
            pg.goto(f'{base}/app/admin', wait_until='networkidle')
            pg.get_by_role('heading', name='Painel da plataforma').wait_for(timeout=15000)
            tirar(pg, 'a11-08-painel-admin.png', 'Painel admin com planos, assinaturas ativas, MRR de teste e eventos')
        else:
            print('[PULADO] a11-08: informe ADMIN_EMAIL e ADMIN_PASSWORD (variáveis de ambiente).')
        nav.close()

    (SAIDA / 'a11-capturas.json').write_text(json.dumps(capturas, ensure_ascii=False, indent=2))
    print(f'{len(capturas)} print(s) em {SAIDA}. Faltam os assistidos: a11-04 (painel da Stripe) e a11-05 (entregas do webhook).')
    return resultado


if __name__ == '__main__':
    sys.exit(main())
