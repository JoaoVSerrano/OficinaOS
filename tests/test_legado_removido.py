"""O domínio antigo (catálogo de filmes, TMDB) foi removido: rotas respondem 404 e o código não o cita mais."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PADRAO = re.compile(r'tom ?hanks|tomhanks|tmdb|filme|movie', re.I)
# Documentos históricos e a revisão baseline podem citar a origem do projeto.
EXCECOES = ('docs/', 'README.md', 'DOCUMENTACAO.md', 'CLAUDE.md', 'backend/migrations/versions/0001_', 'backend/static/',
            'frontend/', 'openapi.', 'tests/test_legado_removido.py', 'tests/test_migracoes.py',
            '.env.example', '.github/', 'docker-compose', 'grafana/', 'demo_',
            'scripts/cenarios/')   # o cenário de aceite procura essas palavras de propósito


@pytest.mark.parametrize('metodo,url', [
    ('get', '/api/catalog'), ('get', '/api/favorites'), ('post', '/api/favorites'), ('delete', '/api/favorites/13'),
    ('get', '/api/comments'), ('post', '/api/comments'), ('delete', '/api/comments/1'),
    ('get', '/api/premium/watchlist'), ('get', '/api/premium/insights'), ('get', '/api/premium/videos'),
])
def test_rotas_antigas_respondem_404(client, metodo, url):
    assert getattr(client, metodo)(url).status_code == 404


def test_codigo_dos_servicos_nao_cita_o_dominio_antigo():
    arquivos = subprocess.run(['git', 'ls-files'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    achados = []
    for rel in arquivos:
        if rel.startswith(EXCECOES) or not rel.endswith(('.py', '.sh', '.yml', '.yaml', '.json', '.sql', '.md')):
            continue
        texto = (ROOT / rel).read_text(encoding='utf-8', errors='ignore')
        if PADRAO.search(texto):
            achados.append(rel)
    assert achados == [], f'citam o domínio antigo: {achados}'
