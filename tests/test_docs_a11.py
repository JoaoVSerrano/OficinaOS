"""T11.9: .env.example só com nomes/placeholders e documentação do fluxo de assinatura."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _variaveis() -> dict[str, str]:
    saida = {}
    for linha in (ROOT / '.env.example').read_text().splitlines():
        if linha.strip() and not linha.lstrip().startswith('#') and '=' in linha:
            k, v = linha.split('=', 1)
            saida[k.strip()] = v.strip()
    return saida


def test_env_example_nao_tem_valor_real_da_stripe():
    texto = (ROOT / '.env.example').read_text()
    assert not re.search(r'\b(sk|pk|rk)_(test|live)_[A-Za-z0-9]{8,}', texto)
    assert not re.search(r'\bwhsec_[A-Za-z0-9]{8,}', texto)
    assert not re.search(r'\bprice_[A-Za-z0-9]{8,}', texto)
    assert 'live_' not in texto


def test_variaveis_da_stripe_estao_presentes_como_placeholder():
    v = _variaveis()
    for nome in ('STRIPE_SECRET_KEY', 'STRIPE_PUBLISHABLE_KEY', 'STRIPE_WEBHOOK_SECRET', 'STRIPE_PRICE_ID',
                 'STRIPE_SUCCESS_URL', 'STRIPE_CANCEL_URL', 'PRO_VALOR_CENTAVOS'):
        assert nome in v, nome
    for nome in ('STRIPE_SECRET_KEY', 'STRIPE_PUBLISHABLE_KEY', 'STRIPE_WEBHOOK_SECRET', 'STRIPE_PRICE_ID'):
        assert v[nome].startswith('troque-'), nome


def test_variaveis_do_compose_do_payment_existem_no_env_example():
    compose = (ROOT / 'docker-compose.yml').read_text()
    v = _variaveis()
    for nome in re.findall(r'(STRIPE_[A-Z_]+|PRO_VALOR_CENTAVOS)\s*:', compose):
        assert nome in v, nome


def test_readme_documenta_assinatura_e_teste_de_webhook():
    r = (ROOT / 'README.md').read_text()
    for trecho in ('stripe listen', '/api/payment/webhook', '4242 4242 4242 4242', 'checkout.session.completed',
                   'customer.subscription.deleted', 'invoice.payment_failed', 'MRR de teste', 'Plano e assinatura'):
        assert trecho in r, trecho
    assert 'github.com/siriani' in r


def test_deploy_md_cobre_urls_de_retorno_e_portal():
    d = (ROOT / 'docs' / 'execucao' / 'DEPLOY.md').read_text()
    assert '/app/plano?assinatura=ok' in d and '/app/plano?assinatura=cancelada' in d
    assert 'cancelamento imediato' in d
