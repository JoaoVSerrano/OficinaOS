from __future__ import annotations

import json
from typing import Any

OPENAPI_SPEC: dict[str, Any] = {
    "openapi": "3.0.3",
    "info": {
        "title": "payment-service — API",
        "description": "API do microsserviço de pagamentos e assinaturas integrado à Stripe.",
        "version": "1.0.0"
    },
    "paths": {
        "/health": {
            "get": {
                "summary": "Health check",
                "responses": {
                    "200": {"description": "Serviço saudável."}
                }
            }
        },
        "/entitlement": {
            "get": {
                "summary": "Verifica se o usuário tem assinatura ativa",
                "parameters": [
                    {"name": "google_id", "in": "query", "required": True, "schema": {"type": "string"}}
                ],
                "responses": {
                    "200": {"description": "Status da assinatura retornado com sucesso."}
                }
            }
        },
        "/checkout": {
            "post": {
                "summary": "Inicia o checkout da assinatura Pro da oficina (customer reutilizado; 409 se já é Pro)",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "oficina_id": {"type": "integer"},
                                    "usuario_id": {"type": "integer"},
                                    "email": {"type": "string"}
                                },
                                "required": ["oficina_id"]
                            }
                        }
                    }
                },
                "responses": {
                    "201": {"description": "Sessão de checkout criada."}
                }
            }
        },
        "/portal": {
            "post": {
                "summary": "Abre o Customer Portal da Stripe",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {"oficina_id": {"type": "integer"}},
                                "required": ["oficina_id"]
                            }
                        }
                    }
                },
                "responses": {
                    "200": {"description": "Portal URL retornado."},
                    "409": {"description": "Oficina sem assinatura (sem customer na Stripe)."}
                }
            }
        },
        "/webhook": {
            "post": {
                "summary": "Webhook da Stripe",
                "responses": {
                    "200": {"description": "Webhook processado com sucesso."}
                }
            }
        }
    }
}

def get_openapi_json() -> str:
    return json.dumps(OPENAPI_SPEC, indent=2, ensure_ascii=False)
