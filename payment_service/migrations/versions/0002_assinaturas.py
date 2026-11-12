"""assinaturas por oficina

Revision ID: 0002_assinaturas
Revises: 0001_payment_init
Create Date: 2026-11-11 10:00:00.000000

"""
from __future__ import annotations
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0002_assinaturas'
down_revision: Union[str, None] = '0001_payment_init'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'assinaturas',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('oficina_id', sa.Integer(), nullable=False),
        sa.Column('usuario_id', sa.Integer(), nullable=True),
        sa.Column('stripe_customer_id', sa.String(length=255), nullable=True),
        sa.Column('stripe_subscription_id', sa.String(length=255), nullable=True),
        sa.Column('plano', sa.String(length=20), server_default='free', nullable=False),
        sa.Column('status', sa.String(length=30), server_default='free', nullable=False),
        sa.Column('valor_mensal_centavos', sa.Integer(), server_default='0', nullable=False),
        sa.Column('moeda', sa.String(length=3), server_default='brl', nullable=False),
        sa.Column('periodo_fim', sa.TIMESTAMP(), nullable=True),
        sa.Column('inadimplente', sa.Boolean(), server_default=sa.text('0'), nullable=False),
        sa.Column('ultimo_evento_em', sa.BigInteger(), nullable=True),
        sa.Column('atualizado_em', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('oficina_id', name='uniq_assinatura_oficina'),
    )
    op.create_index('ix_assinaturas_oficina_id', 'assinaturas', ['oficina_id'])
    op.create_index('ix_assinaturas_stripe_customer_id', 'assinaturas', ['stripe_customer_id'])
    op.create_index('ix_assinaturas_stripe_subscription_id', 'assinaturas', ['stripe_subscription_id'])


def downgrade() -> None:
    op.drop_table('assinaturas')
