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
    "409": "Conflito (regra de negócio)", "410": "Expirado (prazo de validade vencido)",
    "429": "Muitas tentativas; aguarde um minuto", "503": "Serviço dependente indisponível",
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
    "/api/os": {
        "get": _op("Ordens de Serviço", "Listar OS (dono: todas; mecânico: atribuídas; cliente: dos seus veículos)",
                   "dono, mecanico, cliente", "200", ("401", "403", "409")),
        "post": _op("Ordens de Serviço", "Abrir ordem de serviço", "dono, mecanico", "201",
                    ("400", "401", "402", "403", "404", "409", "503"),
                    {"veiculo_id": "integer", "descricao": "string", "mecanico_id": "integer", "km_entrada": "integer"},
                    "No plano Free: 20 OS por mês (402 ao exceder)."),
    },
    "/api/os/{os_id}": {
        "get": _com_id(_op("Ordens de Serviço", "Detalhar OS com itens", "dono, mecanico (atribuída), cliente (própria)",
                           "200", ("401", "403", "404", "409")), "os_id"),
        "put": _com_id(_op("Ordens de Serviço", "Editar descrição, km de entrada e mecânico da OS",
                           "dono, mecanico (atribuída)", "200", ("400", "401", "403", "404", "409", "503"),
                           {"descricao": "string", "mecanico_id": "integer", "km_entrada": "integer"}), "os_id"),
        "delete": _com_id(_op("Ordens de Serviço", "Excluir OS (exclusão lógica; não devolve cota do plano)", "dono",
                              "200", ("401", "403", "404", "409")), "os_id"),
    },
    "/api/os/{os_id}/itens": {"post": _com_id(_op(
        "Ordens de Serviço", "Adicionar item (serviço ou peça); o total é a soma dos itens", "dono, mecanico (atribuída)",
        "201", ("400", "401", "403", "404", "409"),
        {"tipo": "string", "descricao": "string", "quantidade": "integer", "valor_unitario_centavos": "integer"}),
        "os_id")},
    "/api/os/{os_id}/itens/{item_id}": {"delete": {
        **_op("Ordens de Serviço", "Remover item da OS", "dono, mecanico (atribuída)", "200",
              ("401", "403", "404", "409")),
        "parameters": _id("os_id") + _id("item_id")}},
    "/api/os/{os_id}/status": {"post": _com_id(_op(
        "Ordens de Serviço",
        "Mudar o status (aberta → orcamento_aprovado → em_servico → pronta → entregue; cancelada só pelo dono)",
        "aprovar orçamento: dono, cliente; iniciar/finalizar serviço: dono, mecanico; entregar e cancelar: dono",
        "200", ("401", "403", "404", "409"), {"status": "string"},
        "Transição inválida responde 409."), "os_id")},
    "/api/auditoria": {"get": _op(
        "Oficina", "Eventos de negócio da minha oficina (quem, papel, recurso e quando)", "dono", "200",
        ("401", "403", "409", "503"), None,
        "Filtros: acao (tipo de evento, ex.: os.), usuario_id, n, cursor. A oficina é sempre a do usuário logado.")},
    "/api/os/{os_id}/anexos": {
        "get": _com_id(_op("Ordens de Serviço", "Listar anexos (fotos/comprovantes) da OS",
                           "dono, mecanico (atribuída), cliente (própria)", "200", ("401", "403", "404", "409")), "os_id"),
        "post": _com_id({**_op(
            "Ordens de Serviço", "Enviar foto ou comprovante da OS (PNG, JPEG ou WEBP, até 5 MB; campo 'arquivo')",
            "dono, mecanico (atribuída)", "201", ("400", "401", "402", "403", "404", "409", "503"),
            None, "Tipo validado pelo conteúdo. Free: até 3 anexos por OS (402 ao exceder)."),
            "requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {
                "type": "object", "properties": {"arquivo": {"type": "string", "format": "binary"}}}}}}}, "os_id"),
    },
    "/api/os/{os_id}/anexos/{anexo_id}/arquivo": {"get": {
        **_op("Ordens de Serviço", "Ler o arquivo do anexo (bucket privado; só quem vê a OS)",
              "dono, mecanico (atribuída), cliente (própria)", "200", ("401", "403", "404", "409")),
        "parameters": _id("os_id") + _id("anexo_id")}},
    "/api/os/{os_id}/anexos/{anexo_id}": {"delete": {
        **_op("Ordens de Serviço", "Remover anexo", "dono", "200", ("401", "403", "404", "409")),
        "parameters": _id("os_id") + _id("anexo_id")}},
}
