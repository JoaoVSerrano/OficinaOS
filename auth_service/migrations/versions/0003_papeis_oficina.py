"""Papéis do negócio (admin/dono/mecanico/cliente) e vínculo com a oficina.

Revision ID: 0003_papeis_oficina
Revises: 0002_google_oauth

Usuários antigos com papel 'usuario' viram 'dono' sem oficina (onboarding "Crie sua oficina").
O admin continua admin. oficina_id não tem FK: a tabela oficinas vive no gateway.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '0003_papeis_oficina'
down_revision = '0002_google_oauth'
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    cols = [c['name'] for c in insp.get_columns('usuarios')]
    if 'oficina_id' not in cols:
        op.add_column('usuarios', sa.Column('oficina_id', sa.Integer(), nullable=True))
        op.create_index('ix_usuarios_oficina_id', 'usuarios', ['oficina_id'])
    op.execute("UPDATE usuarios SET role = 'dono' WHERE role = 'usuario'")
    op.alter_column('usuarios', 'role', existing_type=sa.String(length=20), nullable=False, server_default='dono')


def downgrade() -> None:
    op.alter_column('usuarios', 'role', existing_type=sa.String(length=20), nullable=False, server_default='usuario')
    op.execute("UPDATE usuarios SET role = 'usuario' WHERE role IN ('dono', 'mecanico', 'cliente')")
    op.drop_index('ix_usuarios_oficina_id', table_name='usuarios')
    op.drop_column('usuarios', 'oficina_id')
