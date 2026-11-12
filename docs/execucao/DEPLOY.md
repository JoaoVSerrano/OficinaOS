# Checklist de deploy (passos do João)

Regras: **mesma stack** do Portainer, mesmo subdomínio, mesmas portas, 1 GB de RAM por container. Não criar stack nova. Nunca colar segredos no chat nem em arquivo versionado.

## 0. Antes do push (a migração é destrutiva)

O push na `main` dispara o CI, que aciona o redeploy; ao subir, o gateway roda a migração `0002_dominio_oficina`, que faz `DROP TABLE` de `favoritos` e `comentarios` no **banco da turma** (e cria as tabelas do domínio novo). O `auth-service` também roda a `0003_papeis_oficina` (usuários `usuario` viram `dono` sem oficina).

- [ ] Backup opcional das tabelas antigas (rode no seu terminal, com as credenciais em variáveis, sem colá-las aqui):
  ```bash
  mysqldump -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p "$DB_NAME" favoritos comentarios usuarios > backup-antes-da-a10.sql
  ```
- [ ] Autorizar o push (`git push origin main`).

## 1. GitHub (repositório OficinaOS)

- [ ] **Settings → Secrets and variables → Actions**: criar `PORTAINER_WEBHOOK_URL` e `DEPLOY_HEALTH_URL` (o `push --mirror` não copia secrets).
- [ ] Conferir que o **Actions** está habilitado.
- [ ] **Packages**: as imagens `oficinaos-app`, `oficinaos-auth-service`, `oficinaos-log-service`, `oficinaos-payment-service` precisam ser acessíveis ao Portainer (visibilidade/permissão do pacote).

## 2. Portainer (mesma stack)

- [ ] **Parar** a stack (Stacks → a stack → Stop).
- [ ] **Remover a rede antiga**: Networks → `<nome-da-stack>_tomhanks-net`. O compose novo usa a rede `oficinaos-net` com a **mesma subnet fixa 10.201.0.0/24**; se a antiga continuar existindo, o redeploy falha com *Pool overlaps*.
- [ ] Trocar o repositório da stack para `https://github.com/JoaoVSerrano/OficinaOS` (branch `main`). Se a versão do Portainer não permitir editar a URL, **pare e avise**: nada de stack nova sem falar com o professor.
- [ ] Variáveis de ambiente:
  - remover `TMDB_API_KEY` e `TMDB_LANGUAGE`;
  - `MINIO_BUCKET_NAME`: o padrão agora é `oficinaos-avatars`. Para **manter as fotos de perfil já enviadas**, deixe `MINIO_BUCKET_NAME=tomhanks-avatars` (e ajuste `MINIO_PUBLIC_URL` se a usar); para começar limpo, apague a variável;
  - `MINIO_ANEXOS_BUCKET` é opcional (padrão `oficinaos-anexos`, bucket privado criado sozinho);
  - o resto fica igual; as variáveis da Stripe estão na seção 4.
- [ ] **Pull and redeploy** e conferir que **todos** os containers ficam `healthy` (o CI também confere o `/health`).

## 3. Verificação no ar (eu faço depois que você avisar)

```bash
gh run watch                                    # CI verde
curl -fsS https://<subdominio>/health
python scripts/cenarios/ativ10.py --base-url https://<subdominio> --admin-email <admin> --admin-password <senha>
```

A senha do admin é a de `AUTH_ADMIN_PASSWORD` da stack: passe-a só no seu terminal (variável `ADMIN_PASSWORD`), nunca no chat.

## 4. Stripe, modo de teste (Atividade 11)

Se `sk_live_`/`pk_live_` aparecer em qualquer lugar, **pare**.

- [ ] Produtos: **Free (R$ 0,00/mês)** e **Pro (R$ 49,00/mês, BRL, recorrente mensal)**; copiar o `price_...` do Pro para `STRIPE_PRICE_ID` na stack.
- [ ] **Customer Portal** (Settings → Billing → Customer portal): permitir **cancelamento imediato** e atualização do cartão.
- [ ] **Webhook** em `https://<subdominio>/api/payment/webhook` com os eventos `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted` e `invoice.payment_failed`; o segredo `whsec_...` vai para `STRIPE_WEBHOOK_SECRET` na stack.
- [ ] `STRIPE_SECRET_KEY` e `STRIPE_PUBLISHABLE_KEY` de **teste** na stack.
- [ ] URLs de retorno do checkout na stack, com o **domínio de produção**: `STRIPE_SUCCESS_URL=https://<subdominio>/app/plano?assinatura=ok` e `STRIPE_CANCEL_URL=https://<subdominio>/app/plano?assinatura=cancelada`. Sem isso o padrão aponta para `localhost`.
- [ ] `FRONTEND_URL=https://<subdominio>` (é para onde o Billing Portal devolve o usuário).
- [ ] `PRO_VALOR_CENTAVOS` é opcional (reserva, padrão 4900): o valor mensal vem do evento da Stripe.
- [ ] Depois do redeploy, o payment-service cria a tabela `assinaturas` sozinho (migração `0002_assinaturas`); nada destrutivo.

## 5. Prints que precisam de você (login em serviços de terceiros)

Painel da Stripe (assinaturas e entregas do webhook), Portainer (stack com containers saudáveis, **sem a aba de variáveis**) e console do MinIO (objeto em `os/...`). Eu abro o navegador visível, você faz o login, e eu capturo só a área sem segredos.
