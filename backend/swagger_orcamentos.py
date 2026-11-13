"""OpenAPI das rotas de backend/orcamentos.py (fragmento mesclado em swagger_spec.OPENAPI_SPEC)."""
from __future__ import annotations

from typing import Any

from backend.swagger_dominio import _com_id, _id, _op  # noqa: F401  (helpers compartilhados)

TAGS: list[dict[str, str]] = [
    {"name": "Orçamento", "description": "Versões do orçamento da OS, decisão pelo app e anotações internas"},
    {"name": "Orçamento público", "description": "Link do orçamento para o cliente: NÃO exige login (o token do "
                                                 "link é a credencial); sem ids nem dados de contato; no-store"},
]

_PUBLICO = ("Rota pública: NÃO exige login. O token do link é a credencial (o banco guarda só o sha256). "
            "Limite de 30 req/min por IP e 10 req/min por token (429). Resposta sempre com Cache-Control: no-store "
            "e sem ids, e-mail, telefone ou notas.")


def _token() -> list[dict[str, Any]]:
    return [{"name": "token", "in": "path", "required": True, "schema": {"type": "string"}}]


def _com(operacao: dict[str, Any], parametros: list[dict[str, Any]]) -> dict[str, Any]:
    operacao["parameters"] = parametros
    return operacao


_DECISAO = {"acao": "string", "motivo": "string"}

PATHS: dict[str, Any] = {
    "/api/os/{os_id}/orcamentos": {
        "get": _com_id(_op("Orçamento", "Listar as versões do orçamento (mais nova primeiro; nunca expõe o token)",
                           "dono, mecanico (atribuídas), cliente (próprias)", "200", ("401", "403", "404", "409")),
                       "os_id"),
        "post": _com_id(_op("Orçamento", "Enviar nova versão do orçamento ao cliente (snapshot dos itens)", "dono",
                            "201", ("400", "401", "403", "404", "409"),
                            {"desconto_centavos": "integer", "validade_dias": "integer",
                             "observacoes_cliente": "string"},
                            "Só com a OS aberta e subtotal > 0. A versão enviada anterior vira 'substituido'. "
                            "Devolve o link relativo /orcamento/<token>, mostrado só nesta resposta."), "os_id"),
    },
    "/api/os/{os_id}/orcamentos/{orcamento_id}/decisao": {
        "post": _com(_op("Orçamento", "Aprovar ou recusar o orçamento pelo app", "dono, cliente (da própria OS)",
                         "200", ("400", "401", "403", "404", "409", "410"), _DECISAO,
                         "acao: 'aprovar' | 'recusar' (motivo de 3 a 500 caracteres). Versão substituída, já "
                         "decidida ou desatualizada => 409; expirada => 410. Aprovar leva a OS a orcamento_aprovado."),
                     _id("os_id") + _id("orcamento_id")),
    },
    "/api/publico/orcamentos/{token}": {
        "get": _com(_op("Orçamento público", "Ver o orçamento pelo link (sem login)", "público (sem login)", "200",
                        ("404", "429"), extra=_PUBLICO), _token()),
    },
    "/api/publico/orcamentos/{token}/decisao": {
        "post": _com(_op("Orçamento público", "Aprovar ou recusar o orçamento pelo link (sem login)",
                         "público (sem login)", "200", ("400", "404", "409", "410", "429"), _DECISAO,
                         _PUBLICO + " Mesmas regras da decisão pelo app; o evento vai para a auditoria da oficina."),
                     _token()),
    },
    "/api/os/{os_id}/notas": {
        "get": _com_id(_op("Orçamento", "Listar anotações internas da OS (o cliente não vê)",
                           "dono, mecanico (atribuídas)", "200", ("401", "403", "404", "409")), "os_id"),
        "post": _com_id(_op("Orçamento", "Adicionar anotação interna", "dono, mecanico (atribuídas)", "201",
                            ("400", "401", "403", "404", "409"), {"texto": "string"}), "os_id"),
    },
}
