"""OpenAPI das rotas de backend/catalogo.py (fragmento mesclado em swagger_spec.OPENAPI_SPEC)."""
from __future__ import annotations

from typing import Any

from backend.swagger_dominio import _com_id, _op

_TAG = "Catálogo"

TAGS: list[dict[str, str]] = [
    {"name": _TAG, "description": "Catálogo de serviços e peças da oficina (tabela de preços, valores em centavos)"},
]

_CORPO = {"tipo": "string", "descricao": "string", "valor_centavos": "integer"}


def _listar() -> dict[str, Any]:
    operacao = _op(_TAG, "Listar itens do catálogo (só os ativos, ordenados por tipo e descrição)",
                   "dono, mecanico (leitura)", "200", ("400", "401", "403", "409"),
                   extra="?todos=1 inclui os inativos, só para o dono (ignorado para o mecânico).")
    operacao["parameters"] = [
        {"name": "todos", "in": "query", "required": False, "schema": {"type": "string", "enum": ["1"]},
         "description": "1 inclui itens inativos (só para o dono)"},
        {"name": "tipo", "in": "query", "required": False, "schema": {"type": "string", "enum": ["servico", "peca"]},
         "description": "Filtra por tipo"},
    ]
    return operacao


PATHS: dict[str, Any] = {
    "/api/catalogo": {
        "get": _listar(),
        "post": _op(_TAG, "Cadastrar item no catálogo (tipo servico|peca, valor em centavos)", "dono", "201",
                    ("400", "401", "403", "409"), _CORPO),
    },
    "/api/catalogo/{item_id}": {
        "put": _com_id(_op(_TAG, "Editar item do catálogo (parcial; ativo=true reativa)", "dono", "200",
                           ("400", "401", "403", "404", "409"), {**_CORPO, "ativo": "boolean"}), "item_id"),
        "delete": _com_id(_op(_TAG, "Desativar item do catálogo (não apaga: OS antigas guardam o preço)", "dono",
                              "200", ("401", "403", "404", "409")), "item_id"),
    },
}
