# CLAUDE.md — OficinaOS

## Contexto
- Disciplina **ISW055 — Introdução à Computação em Nuvem** (Fatec Pompeia, Prof. Allan Siriani, github.com/siriani). Aluno: João Serrano.
- Produto: **OficinaOS**, ordens de serviço para oficinas mecânicas pequenas. Plano de negócio e Lean Canvas no `README.md`.
- Este repositório é um fork com histórico do catálogo de filmes (`tomhanks`). **A remoção de Tom Hanks/filme/TMDB é autorizada na Atividade 10** (plano em `docs/execucao/EXECUCAO.md`, seção 4.9). Só a migração destrutiva (`DROP` de `favoritos`/`comentarios`) exige confirmação antes do push.
- Fase atual: Atividades 10 e 11 e relatório P2 (entrega 13/11/2026 23:59). Plano, decisões e deploy em `docs/execucao/` (`EXECUCAO.md`, `DECISOES.md`, `DEPLOY.md`).
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
- Rodar migração destrutiva no banco da turma (o `DROP` das tabelas de filmes roda sozinho no deploy).

## Desenvolvimento local (A10/A11/P2)
```bash
python3 -m venv venv && . venv/bin/activate && pip install -r requirements.txt -r auth_service/requirements.txt -r log_service/requirements.txt -r payment_service/requirements.txt pytest typst playwright
. .evidencias/envtest.sh && pytest tests/ -v   # envs fictícios do CI (arquivo local, ignorado pelo git)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build   # MariaDB local, nunca o banco da turma
scripts/build_frontend.sh                      # Angular -> backend/static
python -m typst compile docs/p2/P2_ISW055_Joao_Serrano.typ docs/P2_ISW055_Joao_Serrano.pdf
python -m playwright install chromium          # prints: scripts/evidencias/capturar.py
```

## Regras adicionais desta fase
- Stripe só em modo de teste; se aparecer `sk_live_`/`pk_live_`, parar e avisar. Nunca guardar dado de cartão; sempre validar `Stripe-Signature`.
- Datas "realizadas" vêm de `git log` e das issues. Nunca reescrever histórico (`--amend` publicado, `rebase`, `--force`, `GIT_COMMITTER_DATE`).
- Prints: nunca capturar variáveis, chaves, senhas ou tokens; contas de demonstração `@oficinaos.example`.
- `oficina_id` vem sempre do usuário autenticado, nunca de parâmetro. Papel e dono do registro são checados no backend.
- Desvios do plano vão para `docs/execucao/DECISOES.md`.
