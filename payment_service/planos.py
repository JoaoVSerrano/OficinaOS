"""Plano de uma oficina, lido sempre do banco (nunca da Stripe nem de cache)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Assinatura

# Status da Stripe em que o Pro continua valendo.
STATUS_PRO = ('active', 'trialing', 'past_due')


def plano_da_oficina(db: Session, oficina_id: int) -> dict:
    """Oficina sem linha, ou com assinatura que não vale mais, é Free."""
    a = db.scalar(select(Assinatura).where(Assinatura.oficina_id == oficina_id))
    if a is None:
        return {'plano': 'free', 'status': 'free', 'inadimplente': False,
                'periodo_fim': None, 'valor_mensal_centavos': 0}
    pro = a.plano == 'pro' and a.status in STATUS_PRO
    return {'plano': 'pro' if pro else 'free', 'status': a.status, 'inadimplente': bool(a.inadimplente),
            'periodo_fim': a.periodo_fim.isoformat() if a.periodo_fim else None,
            'valor_mensal_centavos': a.valor_mensal_centavos if pro else 0}
