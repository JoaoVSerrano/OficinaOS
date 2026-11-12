#!/bin/sh
# Gera db/001_dominio.sql a partir das migrações do gateway (Alembic em modo offline, sem banco).
set -e
cd "$(dirname "$0")/.."
[ -f venv/bin/activate ] && . venv/bin/activate
export PYTHONPATH=.
export DB_HOST="${DB_HOST:-localhost}" DB_USER="${DB_USER:-x}" DB_PASSWORD="${DB_PASSWORD:-x}" DB_NAME="${DB_NAME:-oficinaos}"
{
  echo "-- OficinaOS: esquema do domínio (gerado por scripts/export_sql.sh; não edite à mão)."
  echo "-- Equivale às revisões Alembic 0001_initial, 0002_dominio_oficina e 0003_oficina_v2 do gateway."
  echo "-- Atenção: remove as tabelas do domínio antigo (favoritos, comentarios), se existirem."
  alembic -c alembic.ini upgrade base:head --sql 2>/dev/null
} > db/001_dominio.sql
echo "db/001_dominio.sql gerado ($(wc -l < db/001_dominio.sql) linhas)"
