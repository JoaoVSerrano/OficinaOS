#!/usr/bin/env python3
"""Cenário de aceite do OficinaOS v2: catálogo, orçamento com link do cliente, notas, pagamento e financeiro.

Uso:  python scripts/cenarios/ativ12.py --base-url http://localhost:8090

Percorre o dia a dia de uma oficina nova: cadastra o catálogo, abre a OS com km, monta o orçamento a partir do
catálogo, envia o link ao cliente (que recusa e depois aprova a versão nova sem login), registra anotações,
recebe o pagamento na entrega e confere o histórico do veículo e o resumo financeiro do mês.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _comum import DOMINIO_CONTAS, SENHA_DEMO, Relatorio, chamar, main_seguro, sessao, sufixo


def cadastrar(base, tipo, nome, email, **extra):
    s = sessao(base)
    r = chamar(s, 'POST', '/api/cadastro', json={'tipo': tipo, 'nome': nome, 'email': email, 'senha': SENHA_DEMO, **extra})
    return s, r


def tem_id(obj) -> bool:
    """Procura qualquer chave terminada em 'id' (ou 'id') em qualquer nível da resposta pública."""
    if isinstance(obj, dict):
        return any(k == 'id' or k.endswith('_id') or tem_id(v) for k, v in obj.items())
    if isinstance(obj, list):
        return any(tem_id(v) for v in obj)
    return False


def executar(base: str) -> int:
    rel = Relatorio()
    sfx = sufixo()
    anon = sessao(base)

    # 0. oficina nova: dono, mecânico e cliente (com veículo)
    dono, r = cadastrar(base, 'dono', 'Dono V2', f'v2dono{sfx}{DOMINIO_CONTAS}', nome_oficina=f'Oficina V2 {sfx}')
    rel.passo('0. Dono cria a oficina', r.status_code == 201, r.text[:120])
    codigo = chamar(dono, 'GET', '/api/oficina').json()['oficina']['codigo_convite']
    mec, r = cadastrar(base, 'mecanico', 'Mecânico V2', f'v2mec{sfx}{DOMINIO_CONTAS}', codigo_convite=codigo)
    mec_id = r.json()['user']['id']
    cli, r = cadastrar(base, 'cliente', 'Cliente V2', f'v2cli{sfx}{DOMINIO_CONTAS}', codigo_convite=codigo)
    rel.passo('0. Mecânico e cliente entram pelo código', r.status_code == 201, r.text[:120])
    cliente_reg = next(c for c in chamar(dono, 'GET', '/api/clientes').json()['clientes'] if c['nome'] == 'Cliente V2')
    r = chamar(dono, 'POST', '/api/veiculos', json={'cliente_id': cliente_reg['id'], 'placa': f'V{sfx[-6:]}',
                                                     'marca': 'VW', 'modelo': 'Gol', 'ano': 2016})
    vei = r.json()['veiculo']['id']

    # 1. catálogo de serviços e peças
    r1 = chamar(dono, 'POST', '/api/catalogo', json={'tipo': 'servico', 'descricao': 'Troca de óleo', 'valor_centavos': 12000})
    r2 = chamar(dono, 'POST', '/api/catalogo', json={'tipo': 'peca', 'descricao': 'Filtro de óleo', 'valor_centavos': 4500})
    rel.passo('1. Dono cadastra serviço e peça no catálogo', r1.status_code == r2.status_code == 201)
    cat = chamar(mec, 'GET', '/api/catalogo')
    rel.passo('1. Mecânico consulta o catálogo', cat.status_code == 200 and len(cat.json()['itens']) == 2)
    rel.passo('1. Mecânico não altera o catálogo (403)',
              chamar(mec, 'POST', '/api/catalogo', json={'tipo': 'peca', 'descricao': 'X', 'valor_centavos': 1}).status_code == 403)
    rel.passo('1. Cliente não vê o catálogo (403)', chamar(cli, 'GET', '/api/catalogo').status_code == 403)

    # 2. OS com km e itens vindos do catálogo
    r = chamar(dono, 'POST', '/api/os', json={'veiculo_id': vei, 'descricao': 'Revisão dos 45 mil', 'km_entrada': 45210,
                                              'mecanico_id': mec_id})
    os_id = r.json()['ordem']['id']
    rel.passo('2. OS aberta com km de entrada', r.status_code == 201 and r.json()['ordem']['km_entrada'] == 45210, r.text[:120])
    for item in cat.json()['itens']:
        chamar(dono, 'POST', f'/api/os/{os_id}/itens', json={'tipo': item['tipo'], 'descricao': item['descricao'],
                                                             'quantidade': 1, 'valor_unitario_centavos': item['valor_centavos']})
    total = chamar(dono, 'GET', f'/api/os/{os_id}').json()['ordem']['valor_total_centavos']
    rel.passo('2. Itens do catálogo somam o total (R$ 165,00)', total == 16500, f'total={total}')

    # 3. orçamento v1: enviado e recusado pelo link
    r = chamar(dono, 'POST', f'/api/os/{os_id}/orcamentos', json={'desconto_centavos': 1500, 'validade_dias': 7,
                                                                  'observacoes_cliente': 'Óleo 5W30 sintético.'})
    link1 = r.json().get('link', '')
    rel.passo('3. Dono envia o orçamento (v1) e recebe o link', r.status_code == 201 and link1.startswith('/orcamento/'), r.text[:120])
    rel.passo('3. Mecânico não envia orçamento (403)', chamar(mec, 'POST', f'/api/os/{os_id}/orcamentos', json={}).status_code == 403)
    r = chamar(cli, 'POST', f'/api/os/{os_id}/status', json={'status': 'orcamento_aprovado'})
    rel.passo('3. Com orçamento enviado, aprovar direto pelo status dá 409', r.status_code == 409)
    token1 = link1.rsplit('/', 1)[-1]
    pub = chamar(anon, 'GET', f'/api/publico/orcamentos/{token1}')
    corpo = pub.json()
    rel.passo('3. Link público abre sem login', pub.status_code == 200 and corpo['orcamento']['total_centavos'] == 15000)
    rel.passo('3. Resposta pública sem ids, e-mail ou telefone', not tem_id(corpo) and 'email' not in pub.text and 'telefone' not in pub.text)
    rel.passo('3. Resposta pública não vai para cache', pub.headers.get('Cache-Control') == 'no-store')
    rel.passo('3. Token inválido -> 404', chamar(anon, 'GET', '/api/publico/orcamentos/token-que-nao-existe').status_code == 404)
    r = chamar(anon, 'POST', f'/api/publico/orcamentos/{token1}/decisao', json={'acao': 'recusar'})
    rel.passo('3. Recusar sem motivo -> 400', r.status_code == 400)
    r = chamar(anon, 'POST', f'/api/publico/orcamentos/{token1}/decisao', json={'acao': 'recusar', 'motivo': 'Achei caro o filtro'})
    rel.passo('3. Cliente recusa pelo link com motivo', r.status_code == 200 and r.json()['orcamento']['status'] == 'recusado', r.text[:120])
    rel.passo('3. A OS continua aberta', chamar(dono, 'GET', f'/api/os/{os_id}').json()['ordem']['status'] == 'aberta')

    # 4. orçamento v2: o link antigo deixa de valer e o novo é aprovado sem login
    r = chamar(dono, 'POST', f'/api/os/{os_id}/orcamentos', json={'desconto_centavos': 2500, 'validade_dias': 3})
    link2 = r.json().get('link', '')
    rel.passo('4. Dono reenvia (v2) com desconto maior', r.status_code == 201 and r.json()['orcamento']['versao'] == 2)
    r = chamar(anon, 'POST', f'/api/publico/orcamentos/{token1}/decisao', json={'acao': 'aprovar'})
    rel.passo('4. Link da v1 não decide mais (409)', r.status_code == 409, f'recebeu {r.status_code}')
    token2 = link2.rsplit('/', 1)[-1]
    r = chamar(anon, 'POST', f'/api/publico/orcamentos/{token2}/decisao', json={'acao': 'aprovar'})
    rel.passo('4. Cliente aprova a v2 pelo link', r.status_code == 200 and r.json()['orcamento']['status'] == 'aprovado', r.text[:120])
    rel.passo('4. A OS foi para "orçamento aprovado"', chamar(dono, 'GET', f'/api/os/{os_id}').json()['ordem']['status'] == 'orcamento_aprovado')
    r = chamar(anon, 'POST', f'/api/publico/orcamentos/{token2}/decisao', json={'acao': 'aprovar'})
    rel.passo('4. Segunda decisão no mesmo link -> 409', r.status_code == 409)
    versoes = chamar(cli, 'GET', f'/api/os/{os_id}/orcamentos').json()['orcamentos']
    rel.passo('4. Cliente vê as versões no app (v2 aprovada, v1 recusada)',
              [(v['versao'], v['status']) for v in versoes] == [(2, 'aprovado'), (1, 'recusado')])
    rel.passo('4. O app nunca expõe o token', token2 not in chamar(dono, 'GET', f'/api/os/{os_id}/orcamentos').text)

    # 5. anotações internas
    r = chamar(mec, 'POST', f'/api/os/{os_id}/notas', json={'texto': 'Cliente pediu para guardar o filtro velho.'})
    rel.passo('5. Mecânico registra anotação interna', r.status_code == 201)
    rel.passo('5. Dono lê as anotações', len(chamar(dono, 'GET', f'/api/os/{os_id}/notas').json()['notas']) == 1)
    rel.passo('5. Cliente não lê anotações internas (403)', chamar(cli, 'GET', f'/api/os/{os_id}/notas').status_code == 403)

    # 6. serviço, pagamento e entrega
    for destino in ('em_servico', 'pronta'):
        chamar(mec, 'POST', f'/api/os/{os_id}/status', json={'status': destino})
    rel.passo('6. Mecânico executa e marca como pronta', chamar(dono, 'GET', f'/api/os/{os_id}').json()['ordem']['status'] == 'pronta')
    r = chamar(dono, 'POST', f'/api/os/{os_id}/pagamentos', json={'valor_centavos': 5000, 'forma': 'pix'})
    rel.passo('6. Pagamento parcial em Pix', r.status_code == 201 and r.json()['saldo_centavos'] == 14000 - 5000, r.text[:140])
    r = chamar(dono, 'POST', f'/api/os/{os_id}/pagamentos', json={'valor_centavos': 999999, 'forma': 'dinheiro'})
    rel.passo('6. Pagar mais que o saldo -> 409', r.status_code == 409)
    rel.passo('6. Mecânico não registra pagamento (403)',
              chamar(mec, 'POST', f'/api/os/{os_id}/pagamentos', json={'valor_centavos': 1, 'forma': 'pix'}).status_code == 403)
    r = chamar(dono, 'POST', f'/api/os/{os_id}/pagamentos', json={'valor_centavos': 9000, 'forma': 'dinheiro'})
    rel.passo('6. Restante em dinheiro quita a OS (desconto do orçamento aplicado)', r.status_code == 201 and r.json()['saldo_centavos'] == 0)
    r = chamar(dono, 'POST', f'/api/os/{os_id}/status', json={'status': 'entregue'})
    rel.passo('6. Veículo entregue com data de entrega', r.status_code == 200 and r.json()['ordem']['entregue_em'])

    # 7. histórico do veículo e resumo financeiro
    h = chamar(cli, 'GET', f'/api/veiculos/{vei}/historico')
    hc = h.json()
    rel.passo('7. Cliente vê o histórico do próprio veículo com o km', h.status_code == 200 and hc.get('ultimo_km') == 45210)
    rel.passo('7. Histórico do cliente não mostra pagamentos', 'pago_centavos' not in h.text and 'valor_devido_centavos' not in h.text)
    hd = chamar(dono, 'GET', f'/api/veiculos/{vei}/historico').json()
    rel.passo('7. Dono vê pago e devido no histórico', hd['ordens'][0].get('pago_centavos') == 14000)
    res = chamar(dono, 'GET', '/api/financeiro/resumo').json()
    rel.passo('7. Resumo do mês: faturado R$ 140,00 (Pix 50 + dinheiro 90)',
              res.get('faturado_centavos') == 14000 and res.get('por_forma') == {'pix': 5000, 'dinheiro': 9000}, str(res)[:160])
    rel.passo('7. Resumo do mês: 1 OS entregue, ticket médio R$ 140,00, nada a receber',
              res.get('os_entregues') == 1 and res.get('ticket_medio_centavos') == 14000 and res.get('a_receber_centavos') == 0)
    rel.passo('7. Mecânico não vê o financeiro (403)', chamar(mec, 'GET', '/api/financeiro/resumo').status_code == 403)

    # 8. auditoria da oficina
    acoes = {e['acao'] for e in chamar(dono, 'GET', '/api/auditoria', params={'n': 200}).json().get('logs', [])}
    esperado = {'catalogo.item_criado', 'orcamento.enviado', 'orcamento.recusado', 'orcamento.aprovado',
                'os.nota_adicionada', 'pagamento.registrado', 'os.entregue'}
    rel.passo('8. A auditoria da oficina registra o fluxo (inclusive as decisões pelo link)', esperado <= acoes,
              str(sorted(esperado - acoes)))
    return rel.concluir()


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base-url', required=True)
    a = ap.parse_args()
    main_seguro(lambda: executar(a.base_url))
