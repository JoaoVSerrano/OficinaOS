from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Baseline neutro.

    Esta revisão criava as tabelas do catálogo de filmes (favoritos, comentarios).
    O domínio mudou para o OficinaOS: o histórico antigo está no git (commit 96b2297).
    Bancos já na revisão 0001 seguem para 0002_dominio_oficina, que remove essas tabelas;
    bancos novos não criam mais nada aqui.
    """


def downgrade() -> None:
    """Nada a desfazer: o baseline não cria tabelas."""
