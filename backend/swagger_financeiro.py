"""OpenAPI das rotas de backend/financeiro.py (fragmento mesclado em swagger_spec.OPENAPI_SPEC)."""
from __future__ import annotations

from typing import Any

from backend.swagger_dominio import _com_id, _id, _op

_TAG = "Histórico e Financeiro"

TAGS: list[dict[str, str]] = [
    {"name": _TAG, "description": "Histórico do veículo, pagamentos recebidos nas OS e resumo financeiro do mês"},
]

_remover = _op(_TAG, "Remover pagamento da OS", "dono", "200", ("401", "403", "404", "409"))
_remover["parameters"] = _id("os_id") + _id("pagamento_id")

_resumo = _op(_TAG, "Resumo financeiro do mês", "dono", "200", ("400", "401", "403", "409"),
              extra="faturado_centavos soma os pagamentos pelo dia do pagamento (pago_em); os_entregues conta "
                    "pela data de entrega; a_receber_centavos é a posição de hoje, independente do mês.")
_resumo["parameters"] = [{"name": "mes", "in": "query", "required": False,
                          "description": "Mês no formato AAAA-MM (padrão: mês corrente em Brasília)",
                          "schema": {"type": "string", "pattern": r"^\d{4}-(0[1-9]|1[0-2])$"}}]

PATHS: dict[str, Any] = {
    "/api/veiculos/{veiculo_id}/historico": {"get": _com_id(_op(
        _TAG, "Histórico de OS do veículo (mais nova primeiro) e último km", "dono, mecanico, cliente",
        "200", ("401", "403", "404", "409"),
        extra="Mecânico vê só as OS atribuídas a ele; cliente só os próprios veículos e nunca recebe valores "
              "pagos ou devidos (esses campos só vão para o dono)."), "veiculo_id")},
    "/api/os/{os_id}/pagamentos": {
        "get": _com_id(_op(_TAG, "Pagamentos da OS com valor devido, pago e saldo", "dono", "200",
                           ("401", "403", "404", "409")), "os_id"),
        "post": _com_id(_op(_TAG, "Registrar pagamento (OS pronta ou entregue; não passa do saldo)", "dono", "201",
                            ("400", "401", "403", "404", "409"),
                            {"valor_centavos": "integer", "forma": "string", "pago_em": "string",
                             "observacao": "string"},
                            extra="forma: dinheiro, pix, cartao_credito, cartao_debito, boleto ou outro. pago_em "
                                  "opcional (AAAA-MM-DD, padrão hoje; não pode ser futura)."), "os_id"),
    },
    "/api/os/{os_id}/pagamentos/{pagamento_id}": {"delete": _remover},
    "/api/financeiro/resumo": {"get": _resumo},
}
