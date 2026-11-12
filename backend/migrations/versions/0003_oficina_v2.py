"""OficinaOS v2: orçamentos com versões, notas internas, catálogo, pagamentos e km.

Só adiciona tabelas e colunas (nada destrutivo).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '0003_oficina_v2'
down_revision = '0002_dominio_oficina'
branch_labels = None
depends_on = None

_OPTS = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}


def _ts(name: str) -> sa.Column:
    return sa.Column(name, sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'))


def _os_fk() -> sa.Column:
    return sa.Column('os_id', sa.Integer(), sa.ForeignKey('ordens_servico.id'), nullable=False)


def upgrade() -> None:
    op.add_column('ordens_servico', sa.Column('km_entrada', sa.Integer(), nullable=True))
    op.add_column('ordens_servico', sa.Column('entregue_em', sa.TIMESTAMP(), nullable=True))

    op.create_table(
        'orcamentos',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        _os_fk(),
        sa.Column('versao', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(16), nullable=False, server_default='enviado'),
        sa.Column('itens_json', sa.Text(), nullable=False),
        sa.Column('subtotal_centavos', sa.BigInteger(), nullable=False),
        sa.Column('desconto_centavos', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('total_centavos', sa.BigInteger(), nullable=False),
        sa.Column('validade_ate', sa.Date(), nullable=False),
        sa.Column('observacoes_cliente', sa.Text(), nullable=True),
        sa.Column('token_hash', sa.String(64), nullable=False, unique=True),
        _ts('enviado_em'),
        sa.Column('decidido_em', sa.TIMESTAMP(), nullable=True),
        sa.Column('decidido_por_usuario_id', sa.Integer(), nullable=True),
        sa.Column('decidido_via', sa.String(8), nullable=True),
        sa.Column('motivo_recusa', sa.String(500), nullable=True),
        sa.Column('criado_por', sa.Integer(), nullable=False),
        sa.UniqueConstraint('os_id', 'versao', name='uniq_orcamento_versao'),
        **_OPTS,
    )
    op.create_index('ix_orcamentos_os_id', 'orcamentos', ['os_id'])

    op.create_table(
        'notas_os',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        _os_fk(),
        sa.Column('autor_id', sa.Integer(), nullable=False),
        sa.Column('texto', sa.Text(), nullable=False),
        _ts('criada_em'),
        **_OPTS,
    )
    op.create_index('ix_notas_os_os_id', 'notas_os', ['os_id'])

    op.create_table(
        'catalogo_itens',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('oficina_id', sa.Integer(), sa.ForeignKey('oficinas.id'), nullable=False),
        sa.Column('tipo', sa.String(10), nullable=False),
        sa.Column('descricao', sa.String(255), nullable=False),
        sa.Column('valor_centavos', sa.BigInteger(), nullable=False),
        sa.Column('ativo', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        _ts('criado_em'),
        **_OPTS,
    )
    op.create_index('ix_catalogo_itens_oficina_id', 'catalogo_itens', ['oficina_id'])

    op.create_table(
        'pagamentos_os',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        _os_fk(),
        sa.Column('valor_centavos', sa.BigInteger(), nullable=False),
        sa.Column('forma', sa.String(16), nullable=False),
        sa.Column('pago_em', sa.Date(), nullable=False),
        sa.Column('registrado_por', sa.Integer(), nullable=False),
        sa.Column('observacao', sa.String(255), nullable=True),
        _ts('criado_em'),
        **_OPTS,
    )
    op.create_index('ix_pagamentos_os_os_id', 'pagamentos_os', ['os_id'])


def downgrade() -> None:
    for t in ('pagamentos_os', 'catalogo_itens', 'notas_os', 'orcamentos'):
        op.drop_table(t)
    op.drop_column('ordens_servico', 'entregue_em')
    op.drop_column('ordens_servico', 'km_entrada')
