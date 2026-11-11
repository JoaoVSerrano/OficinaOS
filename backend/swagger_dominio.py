"""Documentação OpenAPI das rotas do domínio da oficina (mesclada em swagger_spec.OPENAPI_SPEC)."""
from __future__ import annotations

from typing import Any

TAGS = [
    {"name": "Oficina", "description": "Cadastro, oficina, equipe e código de convite"},
    {"name": "Clientes e Veículos", "description": "Clientes da oficina e seus veículos (escopo por oficina)"},
    {"name": "Ordens de Serviço", "description": "Ordens de serviço, itens, status e anexos (MinIO)"},
    {"name": "Planos e Assinatura", "description": "Planos Free/Pro, checkout, portal e webhooks (Stripe, modo de teste)"},
]

_MSG = {
    "200": "Sucesso", "201": "Criado", "400": "Dados inválidos",
    "401": "Não autenticado", "402": "Limite do plano atingido (codigo=limite_plano)",
    "403": "Papel sem permissão para esta ação", "404": "Registro não encontrado (ou de outra oficina)",
    "409": "Conflito (regra de negócio)", "503": "Serviço dependente indisponível",
}


def _op(tag: str, summary: str, papeis: str, ok: str = "200", erros: tuple[str, ...] = ("401", "403"),
        corpo: dict[str, Any] | None = None, extra: str = "") -> dict[str, Any]:
    operacao: dict[str, Any] = {
        "tags": [tag],
        "summary": summary,
        "description": f"Papéis permitidos: {papeis}. A permissão é verificada no backend. {extra}".strip(),
        "responses": {ok: {"description": _MSG[ok]}, **{c: {"description": _MSG[c]} for c in erros}},
    }
    if corpo:
        operacao["requestBody"] = {"required": True, "content": {"application/json": {"schema": {
            "type": "object", "properties": {k: {"type": v} for k, v in corpo.items()}}}}}
    return operacao


def _id(nome: str) -> list[dict[str, Any]]:
    return [{"name": nome, "in": "path", "required": True, "schema": {"type": "integer"}}]


def _com_id(operacao: dict[str, Any], nome: str) -> dict[str, Any]:
    operacao["parameters"] = _id(nome)
    return operacao


PATHS: dict[str, Any] = {
    "/api/cadastro": {"post": {
        **_op("Oficina", "Cadastro orquestrado (dono cria a oficina; mecânico/cliente entram por convite)", "público",
              "201", ("400", "402", "409", "503"),
              {"tipo": "string", "nome": "string", "email": "string", "senha": "string",
               "nome_oficina": "string", "codigo_convite": "string"}),
    }},
    "/api/oficinas": {"post": _op("Oficina", "Criar a oficina (onboarding do dono sem oficina)", "dono", "201",
                                  ("400", "401", "403", "503"), {"nome": "string"})},
    "/api/oficina": {"get": _op("Oficina", "Dados da minha oficina e plano (o dono vê o código de convite)",
                                "dono, mecanico, cliente", "200", ("401", "403", "404", "409"))},
    "/api/equipe": {"get": _op("Oficina", "Equipe da oficina", "dono", "200", ("401", "403", "409", "503"))},
    "/api/clientes": {
        "get": _op("Clientes e Veículos", "Listar clientes da oficina", "dono, mecanico (leitura)", "200",
                   ("401", "403", "409")),
        "post": _op("Clientes e Veículos", "Cadastrar cliente", "dono", "201", ("400", "401", "403", "409"),
                    {"nome": "string", "telefone": "string", "email": "string"}),
    },
    "/api/clientes/{cliente_id}": {
        "get": _com_id(_op("Clientes e Veículos", "Detalhar cliente", "dono, mecanico", "200",
                           ("401", "403", "404", "409")), "cliente_id"),
        "put": _com_id(_op("Clientes e Veículos", "Editar cliente", "dono", "200", ("400", "401", "403", "404", "409"),
                           {"nome": "string", "telefone": "string", "email": "string"}), "cliente_id"),
        "delete": _com_id(_op("Clientes e Veículos", "Remover cliente (sem veículos)", "dono", "200",
                              ("401", "403", "404", "409")), "cliente_id"),
    },
    "/api/veiculos": {
        "get": _op("Clientes e Veículos", "Listar veículos (o cliente vê só os próprios)", "dono, mecanico, cliente",
                   "200", ("401", "403", "409")),
        "post": _op("Clientes e Veículos", "Cadastrar veículo", "dono", "201", ("400", "401", "403", "404", "409"),
                    {"cliente_id": "integer", "placa": "string", "marca": "string", "modelo": "string", "ano": "integer"}),
    },
    "/api/veiculos/{veiculo_id}": {
        "get": _com_id(_op("Clientes e Veículos", "Detalhar veículo", "dono, mecanico, cliente (só os próprios)", "200",
                           ("401", "403", "404", "409")), "veiculo_id"),
        "put": _com_id(_op("Clientes e Veículos", "Editar veículo", "dono", "200", ("400", "401", "403", "404", "409"),
                           {"placa": "string", "marca": "string", "modelo": "string", "ano": "integer"}), "veiculo_id"),
        "delete": _com_id(_op("Clientes e Veículos", "Remover veículo (sem ordens de serviço)", "dono", "200",
                              ("401", "403", "404", "409")), "veiculo_id"),
    },
}
