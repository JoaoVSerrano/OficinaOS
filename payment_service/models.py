from __future__ import annotations
from datetime import datetime
from sqlalchemy import BigInteger, Boolean, Integer, String, TIMESTAMP, text
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base

class StripeCustomer(Base):
    """Vínculo entre google_id do usuário e customer_id da Stripe."""
    __tablename__ = 'stripe_customers'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    google_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    stripe_customer_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    criado_em: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))

class ProcessedWebhookEvent(Base):
    """Registro de eventos de webhook processados — garante idempotência."""
    __tablename__ = 'processed_webhook_events'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stripe_event_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    processado_em: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))


class Assinatura(Base):
    """Cópia local da assinatura Stripe de uma oficina (atualizada só pelos webhooks)."""
    __tablename__ = 'assinaturas'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    oficina_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    usuario_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    plano: Mapped[str] = mapped_column(String(20), nullable=False, default='free', server_default='free')
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='free', server_default='free')
    valor_mensal_centavos: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default='0')
    moeda: Mapped[str] = mapped_column(String(3), nullable=False, default='brl', server_default='brl')
    periodo_fim: Mapped[datetime | None] = mapped_column(TIMESTAMP, nullable=True)
    inadimplente: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text('0'))
    ultimo_evento_em: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # event.created (epoch)
    atualizado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'), onupdate=text('CURRENT_TIMESTAMP'))
