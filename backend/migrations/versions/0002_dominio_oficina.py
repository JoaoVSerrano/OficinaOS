from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '0002_dominio_oficina'
down_revision = '0001_initial'
branch_labels = None
depends_on = None

_OPTS = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}


def _ts(name: str) -> sa.Column:
    return sa.Column(name, sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'))


def upgrade() -> None:
    # DESTRUTIVO: remove as tabelas do domínio antigo do projeto (favoritos e comentarios). Confirmado pelo dono do repositório.
    op.execute('DROP TABLE IF EXISTS comentarios')
    op.execute('DROP TABLE IF EXISTS favoritos')

    op.create_table(
        'oficinas',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('nome', sa.String(120), nullable=False),
        sa.Column('codigo_convite', sa.String(16), nullable=False, unique=True),
        _ts('criada_em'),
        **_OPTS,
    )
    op.create_table(
        'clientes',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('oficina_id', sa.Integer(), sa.ForeignKey('oficinas.id'), nullable=False),
        sa.Column('usuario_id', sa.Integer(), nullable=True),
        sa.Column('nome', sa.String(120), nullable=False),
        sa.Column('telefone', sa.String(20), nullable=True),
        sa.Column('email', sa.String(160), nullable=True),
        _ts('criado_em'),
        **_OPTS,
    )
    op.create_index('ix_clientes_oficina_id', 'clientes', ['oficina_id'])
    op.create_index('ix_clientes_usuario_id', 'clientes', ['usuario_id'])
    op.create_table(
        'veiculos',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('oficina_id', sa.Integer(), sa.ForeignKey('oficinas.id'), nullable=False),
        sa.Column('cliente_id', sa.Integer(), sa.ForeignKey('clientes.id'), nullable=False),
        sa.Column('placa', sa.String(10), nullable=False),
        sa.Column('marca', sa.String(60), nullable=False),
        sa.Column('modelo', sa.String(60), nullable=False),
        sa.Column('ano', sa.Integer(), nullable=True),
        sa.UniqueConstraint('oficina_id', 'placa', name='uniq_oficina_placa'),
        **_OPTS,
    )
    op.create_index('ix_veiculos_oficina_id', 'veiculos', ['oficina_id'])
    op.create_index('ix_veiculos_cliente_id', 'veiculos', ['cliente_id'])
    op.create_table(
        'ordens_servico',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('oficina_id', sa.Integer(), sa.ForeignKey('oficinas.id'), nullable=False),
        sa.Column('veiculo_id', sa.Integer(), sa.ForeignKey('veiculos.id'), nullable=False),
        sa.Column('mecanico_id', sa.Integer(), nullable=True),
        sa.Column('criada_por', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(24), nullable=False, server_default='aberta'),
        sa.Column('descricao', sa.Text(), nullable=False),
        sa.Column('valor_total_centavos', sa.BigInteger(), nullable=False, server_default='0'),
        _ts('criada_em'),
        sa.Column('atualizada_em', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('excluida_em', sa.TIMESTAMP(), nullable=True),
        **_OPTS,
    )
    op.create_index('ix_ordens_servico_veiculo_id', 'ordens_servico', ['veiculo_id'])
    op.create_index('ix_ordens_servico_mecanico_id', 'ordens_servico', ['mecanico_id'])
    op.create_index('idx_os_oficina_criada', 'ordens_servico', ['oficina_id', 'criada_em'])
    op.create_table(
        'itens_os',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('os_id', sa.Integer(), sa.ForeignKey('ordens_servico.id'), nullable=False),
        sa.Column('tipo', sa.String(10), nullable=False),
        sa.Column('descricao', sa.String(255), nullable=False),
        sa.Column('quantidade', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('valor_unitario_centavos', sa.BigInteger(), nullable=False),
        **_OPTS,
    )
    op.create_index('ix_itens_os_os_id', 'itens_os', ['os_id'])
    op.create_table(
        'anexos_os',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('os_id', sa.Integer(), sa.ForeignKey('ordens_servico.id'), nullable=False),
        sa.Column('chave_objeto', sa.String(255), nullable=False),
        sa.Column('nome_original', sa.String(255), nullable=False),
        sa.Column('tipo_mime', sa.String(60), nullable=False),
        sa.Column('tamanho_bytes', sa.Integer(), nullable=False),
        sa.Column('enviado_por', sa.Integer(), nullable=False),
        _ts('criado_em'),
        **_OPTS,
    )
    op.create_index('ix_anexos_os_os_id', 'anexos_os', ['os_id'])


def downgrade() -> None:
    for t in ('anexos_os', 'itens_os', 'ordens_servico', 'veiculos', 'clientes', 'oficinas'):
        op.drop_table(t)
    # As tabelas antigas não são recriadas: o histórico está no git.
