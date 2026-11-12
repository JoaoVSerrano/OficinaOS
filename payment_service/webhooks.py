"""Efeitos dos webhooks da Stripe sobre `assinaturas`.

O efeito e o registro de idempotência vão na MESMA transação: se o efeito falhar,
nada fica marcado e a Stripe reenvia o evento.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Assinatura, ProcessedWebhookEvent
from .planos import STATUS_PRO

VALOR_PRO_CENTAVOS = int(os.getenv('PRO_VALOR_CENTAVOS', '4900'))


def _int(valor) -> int | None:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def _localizar(db: Session, obj: dict) -> Assinatura | None:
    # evento de assinatura traz o id dela em `id`; o de fatura, em `subscription`
    sub_id = obj.get('subscription') or (obj.get('id') if str(obj.get('id', '')).startswith('sub_') else None)
    if sub_id:
        a = db.scalar(select(Assinatura).where(Assinatura.stripe_subscription_id == sub_id))
        if a:
            return a
    customer = obj.get('customer')
    if customer:
        return db.scalar(select(Assinatura).where(Assinatura.stripe_customer_id == customer))
    return None


def _atrasado(a: Assinatura, criado_em: int) -> bool:
    return a.ultimo_evento_em is not None and criado_em < a.ultimo_evento_em


def _aplicar(db: Session, tipo: str, obj: dict, criado_em: int) -> str | None:
    """Devolve o nome do evento de negócio a registrar no log (ou None)."""
    if tipo == 'checkout.session.completed':
        meta = obj.get('metadata') or {}
        oficina_id = _int(obj.get('client_reference_id')) or _int(meta.get('oficina_id'))
        if oficina_id is None:
            return None
        a = db.scalar(select(Assinatura).where(Assinatura.oficina_id == oficina_id))
        if a is None:
            a = Assinatura(oficina_id=oficina_id)
            db.add(a)
        a.stripe_customer_id = obj.get('customer') or a.stripe_customer_id
        a.stripe_subscription_id = obj.get('subscription') or a.stripe_subscription_id
        a.usuario_id = _int(meta.get('usuario_id')) or a.usuario_id
        if _atrasado(a, criado_em):
            return None
        a.plano, a.status = 'pro', 'active'
        a.valor_mensal_centavos, a.moeda = VALOR_PRO_CENTAVOS, 'brl'
        a.inadimplente = False
        a.ultimo_evento_em = criado_em
        return 'assinatura.ativada'

    a = _localizar(db, obj)
    if a is None or _atrasado(a, criado_em):
        return None

    if tipo == 'customer.subscription.updated':
        status = obj.get('status') or a.status
        a.status = status
        a.plano = 'pro' if status in STATUS_PRO else 'free'
        if a.plano == 'free':
            a.valor_mensal_centavos = 0
        if status == 'active':
            a.inadimplente = False
        fim = _int(obj.get('current_period_end'))
        if fim:
            a.periodo_fim = datetime.fromtimestamp(fim, tz=timezone.utc).replace(tzinfo=None)
        evento = 'assinatura.atualizada'
    elif tipo == 'customer.subscription.deleted':
        a.plano, a.status = 'free', 'canceled'
        a.valor_mensal_centavos, a.inadimplente = 0, False
        evento = 'assinatura.cancelada'
    elif tipo == 'invoice.payment_failed':
        a.inadimplente = True
        evento = 'assinatura.pagamento_falhou'
    else:
        return None
    a.ultimo_evento_em = criado_em
    return evento


def processar_evento(db: Session, event) -> tuple[bool, str | None]:
    """Aplica o evento e o marca como processado. Retorna (novo, evento_de_negocio).

    Não faz commit: quem chama controla a transação (rollback desfaz tudo).
    """
    existente = db.scalar(select(ProcessedWebhookEvent)
                          .where(ProcessedWebhookEvent.stripe_event_id == event['id']))
    if existente:
        return False, None
    negocio = _aplicar(db, event['type'], event['data']['object'], int(event.get('created') or 0))
    db.add(ProcessedWebhookEvent(stripe_event_id=event['id'], event_type=event['type']))
    db.flush()
    return True, negocio
