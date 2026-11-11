"""Migração do domínio da oficina: roda em modo offline (sem banco) e confere o SQL e os modelos."""
from __future__ import annotations

import io
from contextlib import redirect_stdout
from pathlib import Path

from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parent.parent
TABELAS = ('oficinas', 'clientes', 'veiculos', 'ordens_servico', 'itens_os', 'anexos_os')


def _sql_offline() -> str:
    cfg = Config(str(ROOT / 'alembic.ini'))
    buf = io.StringIO()
    with redirect_stdout(buf):
        command.upgrade(cfg, '0001_initial:0002_dominio_oficina', sql=True)
    return buf.getvalue()


def test_migracao_cria_tabelas_do_dominio_com_fks():
    sql = _sql_offline()
    for t in TABELAS:
        assert f'CREATE TABLE {t}' in sql
    assert sql.count('FOREIGN KEY') >= 6
    assert 'uniq_oficina_placa' in sql
    assert 'DROP TABLE IF EXISTS favoritos' in sql
    assert 'DROP TABLE IF EXISTS comentarios' in sql


def test_baseline_nao_cria_tabelas_antigas():
    cfg = Config(str(ROOT / 'alembic.ini'))
    buf = io.StringIO()
    with redirect_stdout(buf):
        command.upgrade(cfg, 'base:0001_initial', sql=True)
    assert 'CREATE TABLE favoritos' not in buf.getvalue()
    assert 'CREATE TABLE comentarios' not in buf.getvalue()


def test_todas_as_tabelas_do_dominio_tem_escopo_de_oficina():
    from backend.models import Base
    for nome in ('clientes', 'veiculos', 'ordens_servico'):
        assert 'oficina_id' in Base.metadata.tables[nome].c
    # itens e anexos chegam à oficina pela OS (os_id -> ordens_servico.oficina_id)
    for nome in ('itens_os', 'anexos_os'):
        assert 'os_id' in Base.metadata.tables[nome].c
    veic = Base.metadata.tables['veiculos']
    uniques = [sorted(c.name for c in u.columns) for u in veic.constraints if u.__class__.__name__ == 'UniqueConstraint']
    assert ['oficina_id', 'placa'] in uniques
