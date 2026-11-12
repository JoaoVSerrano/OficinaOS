"""Planos e limites (README do produto). Dinheiro sempre em centavos."""
from __future__ import annotations

PLANOS = {
    'free': {
        'nome': 'Free',
        'preco_mensal_centavos': 0,
        'max_os_mes': 20,
        'max_mecanicos': 1,
        'max_anexos_por_os': 3,
    },
    'pro': {
        'nome': 'Pro',
        'preco_mensal_centavos': 4900,
        'max_os_mes': None,        # None = sem limite
        'max_mecanicos': None,
        'max_anexos_por_os': None,
    },
}

COMO_LIBERAR = 'Assine o Pro (R$ 49/mês) em Plano e assinatura'


def plano_da_oficina(oficina_id: int) -> str:
    """Plano atual da oficina, consultado ao payment-service (que lê o banco) a CADA chamada.

    Sem cache: quando o webhook muda o plano, a próxima requisição já enxerga. Se o
    payment-service falhar, vale o Free (o lado seguro: nunca libera o que não foi pago).
    """
    from backend import app as core
    try:
        resp = core._forward_to_payment('GET', f'/internal/plano?oficina_id={int(oficina_id)}')
        plano = resp.json().get('plano') if resp.status_code == 200 else None
    except Exception as exc:  # rede, JSON inválido, etc.
        core.app.logger.warning('plano da oficina %s indisponível, assumindo Free: %s', oficina_id, exc)
        return 'free'
    return plano if plano in PLANOS else 'free'


def limite(plano: str, chave: str):
    return PLANOS.get(plano, PLANOS['free'])[chave]
