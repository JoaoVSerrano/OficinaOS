from __future__ import annotations

import json
from typing import Any

OPENAPI_SPEC: dict[str, Any] = {
    "openapi": "3.0.3",
    "info": {
        "title": "OficinaOS — API Specification",
        "description": (
            "Documentação OpenAPI 3.0 / Swagger UI do OficinaOS (ordens de serviço para oficinas mecânicas).\n\n"
            "Inclui todos os microsserviços:\n"
            "- **Oficina**: cadastro, convite, equipe, clientes, veículos, ordens de serviço e anexos (MinIO)\n"
            "- **Autenticação**: Registro, Login, Logout, Sessão e Recuperação de Senha\n"
            "- **Perfil & Upload (MinIO)**: Foto de perfil no Object Storage e Bio\n"
            "- **Planos e Assinatura**: Free e Pro (Stripe, modo de teste)\n"
            "- **Auditoria & Log (Redis Streams)**: eventos de negócio e consulta por oficina\n\n"
            "Professor: Allan Siriani (ISW055 — Introdução à Computação em Nuvem)"
        ),
        "version": "1.0.0",
        "contact": {
            "name": "Allan Siriani (Professor)",
            "url": "https://github.com/siriani"
        }
    },
    "servers": [
        {
            "url": "/",
            "description": "Gateway da Aplicação"
        }
    ],
    "tags": [
        {"name": "Health", "description": "Status de saúde da aplicação"},
        {"name": "Autenticação", "description": "Gerenciamento de contas, login e sessões"},
        {"name": "Perfil & Upload", "description": "Perfil de usuário, biografia e foto no MinIO Object Storage"},
        {"name": "Administração & Auditoria", "description": "Gestão de papéis e logs de auditoria no Redis Streams"}
    ],
    "paths": {
        "/health": {
            "get": {
                "tags": ["Health"],
                "summary": "Healthcheck raiz do sistema",
                "description": "Verifica se a aplicação Flask e suas dependências estão funcionando corretamente.",
                "responses": {
                    "200": {
                        "description": "Sistema operando normalmente",
                        "content": {
                            "application/json": {
                                "example": {"status": "healthy"}
                            }
                        }
                    },
                    "503": {
                        "description": "Dependência degradada",
                        "content": {
                            "application/json": {
                                "example": {"status": "unhealthy"}
                            }
                        }
                    }
                }
            }
        },
        "/api/health": {
            "get": {
                "tags": ["Health"],
                "summary": "Healthcheck do sistema",
                "description": "Verifica se a aplicação Flask e o gateway estão funcionando corretamente.",
                "responses": {
                    "200": {
                        "description": "Sistema operando normalmente",
                        "content": {
                            "application/json": {
                                "example": {"ok": True}
                            }
                        }
                    }
                }
            }
        },
        "/api/auth/register": {
            "post": {
                "tags": ["Autenticação"],
                "summary": "Criar nova conta de usuário",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["nome", "email", "senha"],
                                "properties": {
                                    "nome": {"type": "string", "example": "Alice Santos"},
                                    "email": {"type": "string", "example": "alice@exemplo.com"},
                                    "senha": {"type": "string", "example": "senha123456"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "201": {
                        "description": "Conta criada com sucesso",
                        "content": {
                            "application/json": {
                                "example": {
                                    "user": {
                                        "id": 7,
                                        "nome": "Alice Santos",
                                        "email": "alice@exemplo.com",
                                        "role": "usuario",
                                        "bio": "",
                                        "avatar_key": None,
                                        "avatar_url": None,
                                        "criado_em": "2026-09-30T22:59:51"
                                    }
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Dados de entrada inválidos",
                        "content": {"application/json": {"example": {"error": "Informe um e-mail válido."}}}
                    },
                    "409": {
                        "description": "Conflito: e-mail já cadastrado",
                        "content": {"application/json": {"example": {"error": "Já existe uma conta com esse e-mail."}}}
                    }
                }
            }
        },
        "/api/auth/login": {
            "post": {
                "tags": ["Autenticação"],
                "summary": "Realizar login e iniciar sessão",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["email", "senha"],
                                "properties": {
                                    "email": {"type": "string", "example": "alice@exemplo.com"},
                                    "senha": {"type": "string", "example": "senha123456"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Login realizado com sucesso",
                        "content": {
                            "application/json": {
                                "example": {
                                    "user": {
                                        "id": 7,
                                        "nome": "Alice Santos",
                                        "email": "alice@exemplo.com",
                                        "role": "usuario",
                                        "bio": "Entusiasta de cinema.",
                                        "avatar_key": "avatar_7_1790809193.png",
                                        "avatar_url": "/api/profile/avatar/avatar_7_1790809193.png",
                                        "criado_em": "2026-09-30T22:59:51"
                                    }
                                }
                            }
                        }
                    },
                    "401": {
                        "description": "Credenciais inválidas",
                        "content": {"application/json": {"example": {"error": "Credenciais inválidas."}}}
                    }
                }
            }
        },
        "/api/auth/logout": {
            "post": {
                "tags": ["Autenticação"],
                "summary": "Encerrar sessão atual",
                "responses": {
                    "200": {
                        "description": "Sessão encerrada",
                        "content": {"application/json": {"example": {"ok": True}}}
                    }
                }
            }
        },
        "/api/auth/me": {
            "get": {
                "tags": ["Autenticação"],
                "summary": "Obter dados do usuário logado na sessão",
                "responses": {
                    "200": {
                        "description": "Usuário autenticado",
                        "content": {
                            "application/json": {
                                "example": {
                                    "user": {
                                        "id": 7,
                                        "nome": "Alice Santos",
                                        "email": "alice@exemplo.com",
                                        "role": "dono",
                                        "oficina_id": 3,
                                        "bio": "Dono da oficina",
                                        "avatar_url": "/api/profile/avatar/avatar_7_1790809193.png"
                                    }
                                }
                            }
                        }
                    },
                    "401": {
                        "description": "Não autenticado",
                        "content": {"application/json": {"example": {"user": None}}}
                    }
                }
            }
        },
        "/api/auth/forgot-password": {
            "post": {
                "tags": ["Autenticação"],
                "summary": "Solicitar link de recuperação de senha por e-mail",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["email"],
                                "properties": {
                                    "email": {"type": "string", "example": "alice@exemplo.com"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "E-mail de recuperação enviado",
                        "content": {
                            "application/json": {
                                "example": {"ok": True, "message": "Se o e-mail existir, enviamos instruções para redefinição."}
                            }
                        }
                    }
                }
            }
        },
        "/api/auth/reset-password": {
            "post": {
                "tags": ["Autenticação"],
                "summary": "Redefinir senha com token",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["token", "nova_senha"],
                                "properties": {
                                    "token": {"type": "string"},
                                    "nova_senha": {"type": "string"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {"description": "Senha redefinida com sucesso"},
                    "400": {"description": "Token inválido ou expirado"}
                }
            }
        },
        "/api/auth/reset-password/check": {
            "get": {
                "tags": ["Autenticação"],
                "summary": "Verificar validade do token de reset",
                "parameters": [
                    {
                        "name": "token",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "string"}
                    }
                ],
                "responses": {
                    "200": {"description": "Token válido"},
                    "400": {"description": "Token inválido ou expirado"}
                }
            }
        },
        "/api/profile/{user_id}": {
            "get": {
                "tags": ["Perfil & Upload"],
                "summary": "Consultar perfil completo do usuário e seus favoritos",
                "parameters": [
                    {
                        "name": "user_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                        "example": 7
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Perfil retornado (só o próprio usuário, admin ou alguém da mesma oficina; senão 404)",
                        "content": {
                            "application/json": {
                                "example": {
                                    "user": {
                                        "id": 7,
                                        "nome": "Alice Santos",
                                        "email": "alice@exemplo.com",
                                        "role": "dono",
                                        "oficina_id": 3,
                                        "bio": "Dono da oficina",
                                        "avatar_key": "avatar_7_1790809193.png",
                                        "avatar_url": "/api/profile/avatar/avatar_7_1790809193.png",
                                        "criado_em": "2026-09-30T22:59:51"
                                    }
                                }
                            }
                        }
                    },
                    "404": {
                        "description": "Usuário não encontrado",
                        "content": {"application/json": {"example": {"error": "Usuário não encontrado."}}}
                    }
                }
            },
            "put": {
                "tags": ["Perfil & Upload"],
                "summary": "Atualizar perfil de usuário (nome e bio)",
                "description": "Permite que um usuário atualize seu próprio nome e biografia. Tentativas de alterar o perfil de terceiros retornam 403 Forbidden.",
                "parameters": [
                    {
                        "name": "user_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                        "example": 7
                    }
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "nome": {"type": "string", "example": "Alice Santos Cloud"},
                                    "bio": {"type": "string", "example": "Engenheira Cloud & Entusiasta de cinema."}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Perfil atualizado",
                        "content": {
                            "application/json": {
                                "example": {
                                    "ok": True,
                                    "user": {
                                        "id": 7,
                                        "nome": "Alice Santos Cloud",
                                        "bio": "Engenheira Cloud & Entusiasta de cinema."
                                    }
                                }
                            }
                        }
                    },
                    "401": {
                        "description": "Não autenticado",
                        "content": {"application/json": {"example": {"error": "Faça login para continuar."}}}
                    },
                    "403": {
                        "description": "Acesso negado: tentativa de editar o perfil de outro usuário",
                        "content": {"application/json": {"example": {"error": "Você não tem permissão para editar este perfil."}}}
                    }
                }
            }
        },
        "/api/profile/{user_id}/avatar": {
            "post": {
                "tags": ["Perfil & Upload"],
                "summary": "Upload de foto de perfil no MinIO Object Storage",
                "description": "Envia um arquivo de imagem (PNG, JPG, WEBP, GIF até 5MB) para o bucket de objetos MinIO. Tentativas de enviar para outro usuário retornam 403 Forbidden.",
                "parameters": [
                    {
                        "name": "user_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                        "example": 7
                    }
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "multipart/form-data": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "avatar": {
                                        "type": "string",
                                        "format": "binary",
                                        "description": "Arquivo de imagem (máx 5MB)"
                                    }
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Imagem enviada e armazenada com sucesso no MinIO",
                        "content": {
                            "application/json": {
                                "example": {
                                    "ok": True,
                                    "user": {
                                        "id": 7,
                                        "avatar_key": "avatar_7_1790809193.png",
                                        "avatar_url": "/api/profile/avatar/avatar_7_1790809193.png"
                                    }
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Arquivo inválido ou tamanho excedido",
                        "content": {"application/json": {"example": {"error": "O tamanho da imagem excede o limite de 5MB."}}}
                    },
                    "403": {
                        "description": "Acesso negado ao enviar foto para perfil alheio",
                        "content": {"application/json": {"example": {"error": "Você não tem permissão para editar este perfil."}}}
                    }
                }
            }
        },
        "/api/profile/avatar/{key}": {
            "get": {
                "tags": ["Perfil & Upload"],
                "summary": "Obter/Servir imagem de perfil diretamente do MinIO",
                "parameters": [
                    {
                        "name": "key",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                        "example": "avatar_7_1790809193.png"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Arquivo binário da imagem (image/png, image/jpeg, etc.)",
                        "content": {
                            "image/png": {},
                            "image/jpeg": {},
                            "image/webp": {}
                        }
                    },
                    "404": {
                        "description": "Avatar não encontrado no MinIO",
                        "content": {"application/json": {"example": {"error": "Avatar não encontrado."}}}
                    }
                }
            }
        },
        "/api/admin/users": {
            "get": {
                "tags": ["Administração & Auditoria"],
                "summary": "Listar todos os usuários (Apenas Admin)",
                "responses": {
                    "200": {
                        "description": "Lista de usuários",
                        "content": {
                            "application/json": {
                                "example": {
                                    "users": [
                                        {"id": 1, "nome": "Admin", "email": "admin@local", "role": "admin"},
                                        {"id": 7, "nome": "Alice Santos", "email": "alice@exemplo.com", "role": "usuario"}
                                    ]
                                }
                            }
                        }
                    },
                    "403": {
                        "description": "Acesso negado para usuários comuns",
                        "content": {"application/json": {"example": {"error": "Acesso negado. Apenas administradores podem executar esta ação."}}}
                    }
                }
            }
        },
        "/api/admin/users/{target_id}/role": {
            "post": {
                "tags": ["Administração & Auditoria"],
                "summary": "Alterar papel do usuário (Promover a Admin ou rebaixar) (Apenas Admin)",
                "parameters": [
                    {
                        "name": "target_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                        "example": 7
                    }
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["role"],
                                "properties": {
                                    "role": {"type": "string", "enum": ["usuario", "admin"], "example": "admin"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Papel alterado com sucesso",
                        "content": {"application/json": {"example": {"ok": True, "user": {"id": 7, "role": "admin"}}}}
                    },
                    "403": {
                        "description": "Acesso negado",
                        "content": {"application/json": {"example": {"error": "Acesso negado."}}}
                    }
                }
            }
        },
        "/api/plano": {
            "get": {
                "tags": ["Planos e Assinatura"],
                "summary": "Plano atual, uso e limites da oficina (dono e mecânico; só o dono gerencia)",
                "responses": {
                    "200": {"description": "plano, status, inadimplente, periodo_fim, valor_mensal_centavos, uso, limites e pode_gerenciar"},
                    "401": {"description": "Sem login"},
                    "403": {"description": "Papel sem acesso (cliente e admin)"},
                },
            }
        },
        "/api/admin/painel": {
            "get": {
                "tags": ["Administração & Auditoria"],
                "summary": "Painel da plataforma: oficinas e usuários por plano, assinaturas ativas, MRR de teste e últimos eventos (Apenas Admin)",
                "responses": {
                    "200": {"description": "Números do painel"},
                    "401": {"description": "Sem login"},
                    "403": {"description": "Papel diferente de admin"},
                    "503": {"description": "Pagamentos ou autenticação indisponíveis"},
                },
            }
        },
        "/api/admin/logs": {
            "get": {
                "tags": ["Administração & Auditoria"],
                "summary": "Consultar logs de auditoria no Redis Streams (Apenas Admin)",
                "parameters": [
                    {
                        "name": "n",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "integer", "default": 50},
                        "description": "Quantidade de registros a retornar (máx 500)"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Lista dos últimos N logs de auditoria gravados no Redis Streams",
                        "content": {
                            "application/json": {
                                "example": {
                                    "count": 2,
                                    "logs": [
                                        {
                                            "event_id": "1790809193000-0",
                                            "usuario_id": 7,
                                            "acao": "avatar_atualizado",
                                            "detalhe": "key=avatar_7_1790809193.png size=120",
                                            "ip": "172.20.0.1",
                                            "ts_ms": 1790809193000
                                        },
                                        {
                                            "event_id": "1790809190000-0",
                                            "usuario_id": 7,
                                            "acao": "login",
                                            "detalhe": "email=alice@exemplo.com",
                                            "ip": "172.20.0.1",
                                            "ts_ms": 1790809190000
                                        }
                                    ]
                                }
                            }
                        }
                    },
                    "403": {
                        "description": "Acesso negado. A tentativa de acesso é gravada no próprio log.",
                        "content": {"application/json": {"example": {"error": "Acesso negado. Apenas administradores podem executar esta ação."}}}
                    }
                }
            }
        },
        "/api/auth/google/url": {
            "get": {
                "tags": ["Autenticação"],
                "summary": "Obter URL de login com Google",
                "responses": {"200": {"description": "URL gerada com sucesso"}}
            }
        },
        "/api/auth/google/callback": {
            "get": {
                "tags": ["Autenticação"],
                "summary": "Callback de autenticação do Google",
                "responses": {"302": {"description": "Redirecionamento para o frontend"}}
            }
        },
        "/api/payment/config": {
            "get": {
                "tags": ["Pagamentos"],
                "summary": "Configurações públicas do Stripe",
                "responses": {"200": {"description": "Configurações retornadas"}}
            }
        },
        "/api/payment/checkout": {
            "post": {
                "tags": ["Pagamentos"],
                "summary": "Iniciar checkout Stripe",
                "responses": {"201": {"description": "Checkout criado"}}
            }
        },
        "/api/payment/portal": {
            "post": {
                "tags": ["Pagamentos"],
                "summary": "Abrir portal do cliente Stripe",
                "responses": {"200": {"description": "URL do portal retornada"}}
            }
        },
        "/api/payment/price": {
            "get": {
                "tags": ["Pagamentos"],
                "summary": "Detalhes e preço do plano premium",
                "responses": {"200": {"description": "Detalhes do plano retornados"}}
            }
        },
        "/api/payment/webhook": {
            "post": {
                "tags": ["Pagamentos"],
                "summary": "Webhook de pagamentos Stripe",
                "responses": {"200": {"description": "Evento processado"}}
            }
        },
        "/api/admin/infra/health": {
            "get": {
                "tags": ["Administração & Auditoria"],
                "summary": "Status de saúde detalhado de todos os microsserviços",
                "responses": {"200": {"description": "Status retornado"}}
            }
        },
        "/api/admin/infra/redis": {
            "get": {
                "tags": ["Administração & Auditoria"],
                "summary": "Informações e estatísticas do Redis",
                "responses": {"200": {"description": "Info retornada"}}
            }
        },
        "/api/admin/infra/swagger-links": {
            "get": {
                "tags": ["Administração & Auditoria"],
                "summary": "Links para o Swagger de cada microsserviço",
                "responses": {"200": {"description": "Links retornados"}}
            }
        }
    }
}


# Rotas do domínio da oficina vivem em fragmentos (um arquivo por módulo de rotas).
from backend import (swagger_catalogo, swagger_dominio, swagger_financeiro,  # noqa: E402
                     swagger_orcamentos)

FRAGMENTOS = (swagger_dominio, swagger_orcamentos, swagger_catalogo, swagger_financeiro)
for _frag in FRAGMENTOS:
    _repetidos = set(_frag.PATHS) & set(OPENAPI_SPEC["paths"])
    assert not _repetidos, f"path documentado duas vezes ({_frag.__name__}): {sorted(_repetidos)}"
    OPENAPI_SPEC["paths"].update(_frag.PATHS)
    OPENAPI_SPEC["tags"].extend(_frag.TAGS)


def get_openapi_json() -> str:
    return json.dumps(OPENAPI_SPEC, indent=2, ensure_ascii=False)


def get_openapi_yaml() -> str:
    try:
        import yaml
        return yaml.dump(OPENAPI_SPEC, allow_unicode=True, sort_keys=False)
    except ImportError:
        # Fallback simples em formato YAML se pyyaml não estiver instalado
        return (
            "openapi: 3.0.3\n"
            "info:\n"
            "  title: OficinaOS — API Specification\n"
            "  version: 1.0.0\n"
            f"  description: '{OPENAPI_SPEC['info']['description']}'\n"
        )
