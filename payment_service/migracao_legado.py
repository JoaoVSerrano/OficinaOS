"""Migração do legado `stripe_customers` (por google_id) para `assinaturas` (por oficina)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Assinatura, StripeCustomer


def legado_para_assinaturas(db: Session, donos: dict[str, tuple[int, int]]) -> int:
    """`donos` mapeia google_id -> (oficina_id, usuario_id). Só migra quem tem oficina.

    O customer é preservado; o plano fica Free até um webhook confirmar a assinatura.
    """
    migrados = 0
    for legado in db.scalars(select(StripeCustomer)).all():
        alvo = donos.get(legado.google_id)
        if not alvo:
            continue
        oficina_id, usuario_id = alvo
        if db.scalar(select(Assinatura).where(Assinatura.oficina_id == oficina_id)):
            continue
        db.add(Assinatura(oficina_id=oficina_id, usuario_id=usuario_id,
                          stripe_customer_id=legado.stripe_customer_id))
        migrados += 1
    db.commit()
    return migrados
