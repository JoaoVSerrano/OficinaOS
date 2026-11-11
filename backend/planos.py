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
    """Plano atual da oficina. Até a Atividade 11 toda oficina é Free."""
    return 'free'


def limite(plano: str, chave: str):
    return PLANOS.get(plano, PLANOS['free'])[chave]
