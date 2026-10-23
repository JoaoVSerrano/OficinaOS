# CLAUDE.md — OficinaOS

## Contexto
- Disciplina **ISW055 — Introdução à Computação em Nuvem** (Fatec Pompeia, Prof. Allan Siriani, github.com/siriani). Aluno: João Serrano.
- Produto: **OficinaOS**, ordens de serviço para oficinas mecânicas pequenas. Plano de negócio e Lean Canvas no `README.md`.
- Este repositório é um fork com histórico do catálogo de filmes (`tomhanks`). **A Atividade 10 fará a limpeza de Tom Hanks/filme/TMDB.** Até lá, não remover nem renomear nada do domínio antigo.
- Idioma: README, documentação e commits em português do Brasil; código em inglês ou como já está no arquivo.

## Serviços (docker-compose, rede `tomhanks-net`)
| Serviço | Porta | Papel |
|---|---|---|
| `app` | 8080 (público) | Gateway Flask + Angular |
| `auth-service` | 3000 | Login, sessão, papéis, perfil, avatar |
| `log-service` | 4000 | Auditoria em Redis Streams |
| `payment-service` | 5000 | Stripe: checkout, webhook, entitlement |
| `redis`, `minio` | internas | Stream/cache e objetos |
| `prometheus`, `grafana` | 9091, 3002 | Métricas e dashboards |
MariaDB é externo (banco da turma). Serviços internos usam `X-Internal-Token`.

## Comandos
```bash
cp .env.example .env && docker compose up -d --build   # subir
pytest tests/ -v                                        # testar (precisa dos envs fictícios do CI)
alembic -c alembic.ini upgrade head                     # migrar gateway (também alembic-auth.ini e alembic-payment.ini)
python scripts/generate_openapi.py                      # regenerar openapi.json/yaml
```

## Convenções
- Conventional Commits (`docs:`, `feat:`, `fix:`, `chore:`), um commit por etapa lógica. Revisar `git diff --staged`; nada de `git add .` cego. Nunca `--force`.
- Rodar os testes antes de commitar. Toda rota nova entra no Swagger (há teste de paridade).

## Segurança
- Sem segredos no repositório; `.env` fica no `.gitignore`.
- Stripe **somente em modo de teste**. Nunca guardar dados de cartão. Sempre validar a assinatura do webhook (`Stripe-Signature`).
- Permissões e dono do registro são checados **sempre no backend**, nunca só na interface.

## Peça confirmação antes de
- `git push` (em qualquer repositório), principalmente no `tomhanks`, que é a evidência da P1.
- Criar issues ou abrir a issue de entrega.
- Mexer no Portainer, em variáveis de produção, no subdomínio ou em chaves Stripe.
- Apagar dados, tabelas ou código do domínio antigo antes da Atividade 10.
