#!/usr/bin/env python3
"""Cenário de aceite da Atividade 11 (SaaS completo), com requests. Nunca usa cartão.

Uso:  python scripts/cenarios/ativ11.py --base-url http://localhost:8090 \
          [--admin-email admin@oficinaos.example --admin-password ...] [--webhook-secret whsec_...]

O que roda sempre: conta Free, limites (21ª OS e 2º mecânico -> 402), papéis (403) e webhook sem
assinatura válida (400). O checkout real só é testado se a Stripe estiver configurada no servidor.

Com --webhook-secret (o segredo de TESTE da stack, via env WEBHOOK_SECRET): o cenário assina e envia
eventos da Stripe e SIMULA o ciclo (assinar -> Pro -> falha de pagamento -> cancelar -> Free). O pagamento
com o cartão 4242 de verdade é feito por scripts/evidencias/checkout.py. Sem credenciais de admin o
painel é pulado.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _comum import DOMINIO_CONTAS, SENHA_DEMO, Relatorio, chamar, main_seguro, sessao, sufixo


def cadastrar(base, tipo, nome, email, **extra):
    s = sessao(base)
    r = chamar(s, 'POST', '/api/cadastro', json={'tipo': tipo, 'nome': nome, 'email': email, 'senha': SENHA_DEMO, **extra})
    return s, r


def enviar_evento(anon, segredo: str, tipo: str, objeto: dict, event_id: str, criado: int):
    """Assina o payload como a Stripe faz (t=<ts>,v1=HMAC-SHA256(segredo, 't.corpo')) e envia ao webhook público."""
    corpo = json.dumps({'id': event_id, 'object': 'event', 'type': tipo, 'created': criado, 'data': {'object': objeto}})
    t = int(time.time())
    assinatura = hmac.new(segredo.encode(), f'{t}.{corpo}'.encode(), hashlib.sha256).hexdigest()
    return chamar(anon, 'POST', '/api/payment/webhook', data=corpo,
                  headers={'Content-Type': 'application/json', 'Stripe-Signature': f't={t},v1={assinatura}'})


def plano(s) -> dict:
    return chamar(s, 'GET', '/api/plano').json()


def executar(base: str, admin_email: str | None, admin_senha: str | None, segredo: str | None) -> int:
    rel = Relatorio()
    sfx = sufixo()
    anon = sessao(base)

    # 1. cria conta: nasce Free
    dono, r = cadastrar(base, 'dono', 'Dona Plano', f'plano{sfx}{DOMINIO_CONTAS}', nome_oficina=f'Oficina Plano {sfx}')
    rel.passo('1. Dono cria conta e oficina', r.status_code == 201, r.text[:120])
    oficina_id = chamar(dono, 'GET', '/api/auth/me').json()['user']['oficina_id']
    p = plano(dono)
    rel.passo('1. A oficina nasce no plano Free', p.get('plano') == 'free' and p.get('nome') == 'Free', str(p)[:120])
    rel.passo('1. Limites do Free: 20 OS, 1 mecânico, 3 anexos',
              p.get('limites') == {'max_os_mes': 20, 'max_mecanicos': 1, 'max_anexos_por_os': 3})
    rel.passo('1. Dono pode gerenciar a assinatura', p.get('pode_gerenciar') is True)
    codigo = chamar(dono, 'GET', '/api/oficina').json()['oficina'].get('codigo_convite', '')

    # 2. papéis: só o dono assina (403 chamando a API direto)
    mec, r = cadastrar(base, 'mecanico', 'Mecânico Plano', f'mec{sfx}{DOMINIO_CONTAS}', codigo_convite=codigo)
    rel.passo('2. Primeiro mecânico entra pelo código', r.status_code == 201, r.text[:120])
    cli, r = cadastrar(base, 'cliente', 'Cliente Plano', f'cli{sfx}{DOMINIO_CONTAS}', codigo_convite=codigo)
    rel.passo('2. Cliente entra pelo código', r.status_code == 201, r.text[:120])
    for quem, s in (('mecânico', mec), ('cliente', cli)):
        rel.passo(f'2. {quem} assinando -> 403', chamar(s, 'POST', '/api/payment/checkout').status_code == 403)
        rel.passo(f'2. {quem} abrindo o portal -> 403', chamar(s, 'POST', '/api/payment/portal').status_code == 403)
    rel.passo('2. Sem login o checkout dá 401', chamar(anon, 'POST', '/api/payment/checkout').status_code == 401)
    rel.passo('2. Mecânico vê o plano mas não gerencia', plano(mec).get('pode_gerenciar') is False)

    # 3. limites do Free no backend
    _, r = cadastrar(base, 'mecanico', 'Mecânico 2', f'mec2{sfx}{DOMINIO_CONTAS}', codigo_convite=codigo)
    corpo = r.json()
    rel.passo('3. 2º mecânico no Free -> 402 com a mensagem do plano',
              r.status_code == 402 and corpo.get('codigo') == 'limite_plano' and corpo.get('limite') == 1
              and 'Pro' in corpo.get('como_liberar', ''), f'{r.status_code} {r.text[:120]}')
    cli_id = chamar(dono, 'POST', '/api/clientes', json={'nome': 'Carlos Plano'}).json()['cliente']['id']
    vei = chamar(dono, 'POST', '/api/veiculos', json={'cliente_id': cli_id, 'placa': f'P{sfx[-6:]}', 'marca': 'VW',
                                                       'modelo': 'Gol', 'ano': 2015}).json()['veiculo']['id']
    criadas = [chamar(dono, 'POST', '/api/os', json={'veiculo_id': vei, 'descricao': f'OS {i}'}).status_code for i in range(20)]
    rel.passo('3. As 20 primeiras OS do mês passam', criadas == [201] * 20, str(criadas))
    rel.passo('3. A tela de plano mostra o uso 20 de 20', plano(dono).get('uso', {}).get('os_mes') == 20)
    r = chamar(dono, 'POST', '/api/os', json={'veiculo_id': vei, 'descricao': 'A 21ª'})
    corpo = r.json()
    rel.passo('3. A 21ª OS é recusada (402) com limite, uso e como liberar',
              r.status_code == 402 and corpo.get('codigo') == 'limite_plano' and corpo.get('limite') == 20
              and corpo.get('uso') == 20 and corpo.get('plano') == 'free' and 'Pro' in corpo.get('como_liberar', ''),
              f'{r.status_code} {r.text[:140]}')

    # 4. webhook: assinatura inválida nunca passa
    r = chamar(anon, 'POST', '/api/payment/webhook', data='{}', headers={'Content-Type': 'application/json'})
    rel.passo('4. Webhook sem assinatura -> 400', r.status_code == 400, f'recebeu {r.status_code}')
    r = chamar(anon, 'POST', '/api/payment/webhook', data='{"type":"checkout.session.completed"}',
               headers={'Content-Type': 'application/json', 'Stripe-Signature': 't=1,v1=assinatura-falsa'})
    rel.passo('4. Webhook com assinatura falsa -> 400', r.status_code == 400, f'recebeu {r.status_code}')
    rel.passo('4. A oficina continua Free depois do webhook falso', plano(dono).get('plano') == 'free')

    # 5. checkout real e portal (exigem a Stripe configurada no servidor)
    r = chamar(dono, 'POST', '/api/payment/portal')
    if r.status_code == 503:
        rel.pular('5. Portal sem assinatura -> 409', 'Stripe não configurada no servidor')
        rel.pular('5. Checkout devolve a URL da Stripe', 'Stripe não configurada no servidor')
    else:
        rel.passo('5. Portal antes de assinar -> 409 com orientação', r.status_code == 409 and 'Assine o Pro' in r.text, r.text[:120])
        r = chamar(dono, 'POST', '/api/payment/checkout')
        url = r.json().get('checkout_url', '') if r.status_code == 201 else ''
        rel.passo('5. Checkout do dono devolve a URL do Checkout da Stripe', url.startswith('https://checkout.stripe.com/'),
                  f'{r.status_code} {r.text[:120]}')
        rel.passo('5. A oficina continua Free até o webhook chegar (retorno do navegador não vale)', plano(dono).get('plano') == 'free')

    # 6. ciclo simulado com eventos assinados (sem cartão)
    if not segredo:
        rel.pular('6. Ciclo simulado Pro -> falha -> Free', 'informe --webhook-secret (segredo de TESTE da stack)')
    else:
        t0 = int(time.time())
        ids = {k: f'evt_cenario_{sfx}_{k}' for k in ('ativa', 'falha', 'cancela')}
        cliente_stripe, assinatura_stripe = f'cus_cenario_{sfx}', f'sub_cenario_{sfx}'
        ativada = {'id': f'cs_cenario_{sfx}', 'customer': cliente_stripe, 'subscription': assinatura_stripe,
                   'client_reference_id': str(oficina_id), 'amount_total': 4900, 'currency': 'brl',
                   'metadata': {'oficina_id': str(oficina_id), 'usuario_id': str(chamar(dono, 'GET', '/api/auth/me').json()['user']['id'])}}
        r = enviar_evento(anon, segredo, 'checkout.session.completed', ativada, ids['ativa'], t0)
        rel.passo('6. Webhook assinado (checkout.session.completed) é aceito', r.status_code == 200, f'{r.status_code} {r.text[:120]}')
        p = plano(dono)
        rel.passo('6. A oficina virou Pro pelo webhook', p.get('plano') == 'pro' and p.get('valor_mensal_centavos') == 4900, str(p)[:140])
        rel.passo('6. No Pro não há limites', all(v is None for v in p.get('limites', {'x': 0}).values()))
        r = chamar(dono, 'POST', '/api/os', json={'veiculo_id': vei, 'descricao': 'A 21ª agora passa'})
        rel.passo('6. A 21ª OS agora passa (201)', r.status_code == 201, f'{r.status_code} {r.text[:100]}')
        _, r = cadastrar(base, 'mecanico', 'Mecânico 2', f'mec2b{sfx}{DOMINIO_CONTAS}', codigo_convite=codigo)
        rel.passo('6. O 2º mecânico agora entra (201)', r.status_code == 201, f'{r.status_code} {r.text[:100]}')
        r = enviar_evento(anon, segredo, 'checkout.session.completed', ativada, ids['ativa'], t0)
        rel.passo('6. Evento repetido é ignorado (idempotência)', r.status_code == 200 and r.json().get('duplicate') is True, r.text[:100])

        if admin_email and admin_senha:
            adm = sessao(base)
            chamar(adm, 'POST', '/api/auth/login', json={'email': admin_email, 'senha': admin_senha})
            pn = chamar(adm, 'GET', '/api/admin/painel')
            d = pn.json() if pn.status_code == 200 else {}
            rel.passo('6. Painel admin: assinaturas ativas e MRR de teste incluem esta oficina',
                      d.get('assinaturas_ativas', 0) >= 1 and d.get('mrr_centavos', 0) >= 4900
                      and d.get('oficinas_por_plano', {}).get('pro', 0) >= 1, str(d)[:160])
            rel.passo('6. Painel admin mostra os últimos eventos', len(d.get('eventos', [])) > 0)
            rel.passo('6. Dono NÃO acessa o painel (403)', chamar(dono, 'GET', '/api/admin/painel').status_code == 403)
        else:
            rel.pular('6. Painel admin (MRR de teste)', 'informe --admin-email e --admin-password')

        r = enviar_evento(anon, segredo, 'invoice.payment_failed', {'customer': cliente_stripe, 'subscription': assinatura_stripe},
                          ids['falha'], t0 + 10)
        rel.passo('6. invoice.payment_failed aceito', r.status_code == 200, r.text[:100])
        rel.passo('6. A oficina fica marcada como inadimplente (continua Pro)',
                  plano(dono).get('inadimplente') is True and plano(dono).get('plano') == 'pro')

        r = enviar_evento(anon, segredo, 'customer.subscription.deleted',
                          {'id': assinatura_stripe, 'customer': cliente_stripe, 'status': 'canceled'}, ids['cancela'], t0 + 20)
        rel.passo('6. customer.subscription.deleted aceito', r.status_code == 200, r.text[:100])
        p = plano(dono)
        rel.passo('6. A oficina voltou ao Free', p.get('plano') == 'free' and p.get('inadimplente') is False, str(p)[:120])
        r = chamar(dono, 'POST', '/api/os', json={'veiculo_id': vei, 'descricao': 'Volta o limite'})
        rel.passo('6. Voltou o limite: nova OS -> 402', r.status_code == 402, f'recebeu {r.status_code}')

    # 7. como admin: o log tem os eventos de plano
    if admin_email and admin_senha:
        adm = sessao(base)
        chamar(adm, 'POST', '/api/auth/login', json={'email': admin_email, 'senha': admin_senha})
        logs = chamar(adm, 'GET', '/api/admin/logs', params={'oficina_id': oficina_id, 'n': 300}).json().get('logs', [])
        acoes = {e['acao'] for e in logs}
        rel.passo('7. O log registra plano.limite_atingido', 'plano.limite_atingido' in acoes, str(sorted(acoes))[:160])
    else:
        rel.pular('7. Eventos de plano no log', 'informe --admin-email e --admin-password')
    return rel.concluir()


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base-url', required=True)
    ap.add_argument('--admin-email', default=os.getenv('ADMIN_EMAIL'))
    ap.add_argument('--admin-password', default=os.getenv('ADMIN_PASSWORD'))
    ap.add_argument('--webhook-secret', default=os.getenv('WEBHOOK_SECRET'))
    a = ap.parse_args()
    main_seguro(lambda: executar(a.base_url, a.admin_email, a.admin_password, a.webhook_secret))
