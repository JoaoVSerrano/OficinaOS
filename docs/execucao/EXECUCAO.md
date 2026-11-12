# Execução: OficinaOS, Atividades 10 e 11 e relatório P2 (ISW055)

> **Como usar (João)**
> 1. `git clone https://github.com/JoaoVSerrano/OficinaOS.git && cd OficinaOS`
> 2. Salve este arquivo como `docs/execucao/EXECUCAO.md` e copie o template do professor para `docs/p2/P2_ISW055_template.typ`.
> 3. Abra o Claude Code na raiz do clone e diga: **"Leia docs/execucao/EXECUCAO.md e execute do início, respeitando os portões de confirmação."**

---

## 0. Missão

Você é o Claude Code trabalhando no repositório do João (GitHub: JoaoVSerrano), aluno da Fatec Pompeia, disciplina **ISW055 — Introdução à Computação em Nuvem**, Prof. Allan Lincoln Rodrigues Siriani (github.com/siriani). O produto é o **OficinaOS**: ordens de serviço para oficinas mecânicas pequenas, nascido como fork com histórico do catálogo de filmes `tomhanks`.

Ao final, o repositório `JoaoVSerrano/OficinaOS` deve estar assim, com tudo enviado ao GitHub:

1. **Atividade 10 no ar:** domínio de oficina no lugar dos filmes, com tabelas e migração/seed versionados, API CRUD, telas, papéis do negócio, isolamento por oficina, eventos de negócio no log, upload no MinIO e landing page pública. Nada de Tom Hanks, filme ou TMDB no código atual.
2. **Atividade 11 no ar:** planos Free e Pro com assinatura recorrente Stripe em modo de teste, quatro webhooks idempotentes, portal do cliente, limites por plano na API e painel admin com MRR de teste.
3. **Testes:** a suíte `pytest` verde, cobrindo permissões, isolamento, limites e webhooks, e o CI verde.
4. **Commits:** um commit pequeno em Conventional Commits a cada etapa.
5. **Prints:** tirados com um navegador real (Playwright), salvos em `docs/p2/prints/`.
6. **Relatório P2 em Typst:** `docs/p2/P2_ISW055_Joao_Serrano.typ`, preenchido a partir do template oficial com os prints anexados, compilado em **`docs/P2_ISW055_Joao_Serrano.pdf`** e linkado no README.
7. **Issues de entrega:** rascunhos prontos de `Entrega — Seu negócio no ar`, `Entrega — SaaS completo` e `Entrega — P2`, abertas só depois da confirmação do João.

---

## 1. Situação real do repositório (verificada em 11/11/2026 num clone de leitura)

Antes de codar, confirme cada item com `git log`, leitura do código e `gh`. Se algo divergir, o repositório vale e você registra a divergência em `docs/execucao/DECISOES.md`.

**Histórico**
- O último commit é `96b2297`, de 23/10/2026 20:25 (`ci: publica imagens como oficinaos-* no GHCR`). **Não há nenhum commit da Atividade 10.**
- São 59 commits, só a branch `main`, sem tags.
- A Atividade 9 foi entregue com `d8abb36` (README do produto, 23/10/2026 20:14), backlog em `docs/backlog-issues.md`, rascunho da issue em `docs/entrega-ativ9.md` e `CLAUDE.md`. Confira com `gh issue list --state all` se a issue `Entrega — Fork e plano de negócio` e as 10 issues do backlog foram realmente abertas, e com que data.

**Serviços** (no `docker-compose.yml`, na rede `tomhanks-net`, subnet fixa `10.201.0.0/24`)
- `app`: gateway Flask com o Angular estático em `backend/static`, porta 8080, o único serviço público.
- `auth-service`: porta 3000.
- `log-service`: porta 4000, grava em Redis Streams `audit:logs`.
- `payment-service`: porta 5000.
- `redis`, `minio` (`cgr.dev/chainguard/minio`), `prometheus` (porta 9091) e `grafana` (porta 3002).
- O MariaDB é **externo** (o banco da turma).
- **Nenhum limite de memória está declarado** no compose.

**Banco e autenticação**
- Há um Alembic por serviço: `alembic.ini` (gateway), `alembic-auth.ini` e `alembic-payment.ini`. As revisões atuais são `0001_initial` (gateway), `0001_auth_init` → `0002_google_oauth` (auth) e `0001_payment_init` (payment).
- **As migrações rodam sozinhas quando os containers sobem:** `ensure_schema()`/`database.py` chama `command.upgrade(config, 'head')`, e auth e payment também chamam `Base.metadata.create_all`. **Portanto, o push que contém uma migração já é o momento em que ela roda no banco da turma**, porque o CI faz o deploy.
- O auth-service usa a tabela `usuarios` com `role` igual a `'usuario'` ou `'admin'` (validação em `/admin/users/<id>/role`), além de `google_id`, `avatar_key` e `reset_tokens`.
- O bucket padrão do MinIO é `tomhanks-avatars`, com política de leitura pública definida em `auth_service/app.py`.

**Pagamento**
- O `payment-service` já tem checkout com `mode='subscription'`, `billing_portal`, webhook validado por `stripe.Webhook.construct_event` e a tabela `processed_webhook_events`.
- **Lacunas para a Atividade 11:**
  - O direito de acesso é consultado **ao vivo na Stripe**, com cache no Redis, e é indexado por `google_id`, ou seja, só funciona para quem entrou com Google.
  - `checkout.session.completed` não grava plano nem assinatura no banco.
  - O evento é marcado como processado **antes** de o efeito acontecer: se o efeito falhar, a Stripe não reenvia.
  - Não existe plano por oficina.

**Gateway**
- `backend/app.py` tem cerca de 1.900 linhas e contém o catálogo (`/api/catalog`), os favoritos, os comentários e as rotas premium de filmes (`/api/premium/watchlist|insights|videos`).
- Também tem os proxies para auth e payment, `require_login`/`require_role`, `log_event`, o painel `/api/admin/infra/*` e o Swagger agregado.

**Frontend**
- Angular 21 em `frontend/front-tom-hanks`, num único componente (`app.ts` com cerca de 870 linhas e `app.html` com cerca de 650), **sem rotas**, com `outputMode: "server"` (SSR).
- O build estático está commitado em `backend/static`, com cerca de 10 bundles `main-*.js` antigos acumulados.

**Testes e CI**
- São 37 testes `pytest`: `test_api`, `test_observability`, `test_payment`, `test_security` e `test_swagger`. O último é um **teste de paridade**: toda rota tem de estar no Swagger.
- O CI (`.github/workflows/ci-cd.yml`) roda os testes, publica no GHCR (`oficinaos-app`, `-auth-service`, `-log-service`, `-payment-service`) e faz o deploy pelo secret `PORTAINER_WEBHOOK_URL`, com smoke test em `DEPLOY_HEALTH_URL`.
- **O `push --mirror` não copia secrets**, então eles precisam existir no OficinaOS.

**Restos do domínio antigo**
- Há ocorrências de `tomhanks`, `filme`, `movie` ou `TMDB` em cerca de 25 arquivos: código, compose, `.env.example`, specs Swagger, `openapi.*`, dashboard do Grafana, scripts `demo_*.sh`, frontend e CI.
- O `CLAUDE.md` atual proíbe remover o domínio antigo "antes da Atividade 10", e é a primeira coisa a atualizar.

### Prazos e penalidades (regras da P2)

| Entrega | Planejada | Situação em 11/11/2026 (confirme) |
|---|---|---|
| A7 Plano Premium | 09/10/2026 | commits de 09/10/2026 22:41–22:45 → **no prazo** |
| A8 SaaS/PaaS/IaaS + documentação | 16/10/2026 | commit `2061f81` em **23/10/2026 19:13** → **com atraso**, salvo se existir commit anterior no `tomhanks` |
| A9 Fork e plano de negócio | 23/10/2026 | README em 23/10/2026 20:14; **a data da issue de entrega decide** |
| A10 Seu negócio no ar | 06/11/2026 | **não iniciada → será "entregue com atraso"** |
| A11 SaaS completo | 13/11/2026 | a fazer, **dentro do prazo** |
| P2 relatório | 13/11/2026 | a fazer; −0,25 por dia depois de 13/11, contado pelo **primeiro commit do PDF em `docs/`** |

Cada atividade de 7 a 11 entregue com atraso ou não entregue desconta 0,25 da P2. **Evidência forjada zera a P2.**

**Prioridade:** a A10 já está atrasada e o desconto é fixo, então o que mais importa é entregar **A11 e P2 até 13/11/2026 23:59 (horário de Brasília)**. Como a A11 depende do domínio da A10, faça a A10 primeiro, mas sem polir além do necessário.

---

## 2. Regras invioláveis

**Segurança**
- Nada de segredo no repositório. O `.env` real fica fora do git e o `.env.example` traz só os nomes.
- Nunca peça segredos no chat: o João os coloca no `.env` local ou no Portainer.
- Stripe **somente em modo de teste**. Se uma chave começar com `sk_live_` ou `pk_live_`, **pare e avise**.
- Nunca guarde dado de cartão: no banco ficam só os IDs de customer e subscription.
- Valide sempre a assinatura do webhook (`Stripe-Signature`).
- Papel e dono do registro são verificados **no backend**, em toda rota.
- O auth-service continua só na rede interna do Docker.

**Honestidade**
- Datas "realizadas" vêm do `git log` e das issues, nunca de estimativa.
- Nunca reescreva o histórico: nada de `--amend` em commit já publicado, `rebase` de commits publicados, `--force` ou `GIT_COMMITTER_DATE`.
- Atividade atrasada é declarada como atrasada. Print é sempre do sistema real.
- Não fabrique telas antigas: se não existir print histórico, use a visão do GitHub no commit da época e diga isso na legenda.

**Git**
- Conventional Commits (`feat`, `fix`, `refactor`, `test`, `docs`, `build`, `ci`, `chore`; escopo opcional; `BREAKING CHANGE:` no rodapé quando for o caso).
- Um commit por etapa lógica pequena, sempre com `pytest` verde antes.
- Revise `git diff --staged` e nada de `git add .` cego.
- Referencie as issues do backlog (`closes #N`) quando fechar uma.

**Peça confirmação do João antes de**
- Qualquer `git push`. Proponha pushes em pontos de checagem, porque cada push na `main` dispara o deploy.
- Criar ou abrir issues.
- Mexer no Portainer, no subdomínio, nas variáveis de produção ou na Stripe.
- Rodar migração destrutiva no banco da turma, como o `DROP` das tabelas de filmes.

**Prints**
- Nunca capture valores de variáveis (o editor de ambiente do Portainer), chaves da Stripe, senhas ou tokens.
- Contas de demonstração usam e-mails `@oficinaos.example`, nunca o e-mail real do João.

**Comportamento**
- Use a lista de tarefas do Claude Code e mantenha a seção 12 deste arquivo marcada (`[x]`).
- Registre decisões e desvios em `docs/execucao/DECISOES.md`.
- Se um passo depende do João, deixe-o listado como pendente e siga com o que não depende dele.
- Nunca diga que algo foi feito, publicado ou testado sem ter a saída do comando que prova.

---

## 3. Fontes oficiais (leia antes de codar)

Leia as quatro páginas abaixo (por WebFetch ou `curl` + extração de texto) e compare com os resumos das seções 3.1 a 3.3. **Se houver divergência, a página vale.**

- A10: https://lapps.studio/disciplinas/introducao-computacao-nuvem/atividades/dominio-no-ar/
- A11: https://lapps.studio/disciplinas/introducao-computacao-nuvem/atividades/saas-completo-stripe/
- P2: https://lapps.studio/disciplinas/introducao-computacao-nuvem/atividades/p2-relatorio-bimestral/
- Template oficial, caso `docs/p2/P2_ISW055_template.typ` não exista: https://lapps.studio/disciplinas/introducao-computacao-nuvem/atividades/p2-relatorio-bimestral/P2_ISW055_template.typ?v=b451c743, e PDF de referência: …/P2_ISW055_template.pdf?v=1a982182

### 3.1 Atividade 10: Seu negócio no ar (planejada para 06/11/2026)

Mesma stack do Portainer, mesmas variáveis de ambiente, mesmo subdomínio e mesmos limites (1 GB de RAM por container). **Não crie stack nova, não peça porta nova, não troque de subdomínio.**

1. A stack existente aponta para o repositório novo (pull + redeploy) e todos os containers ficam rodando e saudáveis.
2. Pelo menos **3 tabelas novas do domínio com chaves estrangeiras**, criadas por **migração + seed versionados** (ex.: `db/001_dominio.sql`). Quem clonar consegue recriar o banco.
3. **API CRUD** do recurso principal (listar, criar, detalhar, editar, remover). O Swagger acompanha as rotas novas.
4. **Telas** de listar, criar, detalhar e editar, com a linguagem do negócio.
5. **Pelo menos 3 papéis** com nomes do negócio no auth-service. Ação proibida responde **403 mesmo chamando a API direto**.
6. **Isolamento:** cada usuário (ou organização) só vê e altera os próprios dados. Abrir o ID de outro dá **403 ou 404**.
7. **Eventos de negócio no log**, com quem e quando. Login e erro continuam sendo registrados.
8. **MinIO ligado ao domínio:** um upload que faz sentido, ligado ao registro certo.
9. **Landing page pública**, sem login, com a proposta de valor e um botão de criar conta.
10. **Nada de Tom Hanks:** saem nomes, textos, rotas, tabelas sem uso e a chave TMDB, inclusive a variável na stack.

**Cenário de teste do professor:**
1. Abre o subdomínio sem login e vê a landing.
2. Cria duas contas de papéis diferentes.
3. Com a 1ª, cria, edita e apaga registros, com upload.
4. Com a 2ª, troca o ID na URL ou chama a API e recebe 403/404.
5. Tenta direto na API uma ação proibida ao seu papel e recebe 403.
6. Como admin, vê no log os eventos com quem e quando.
7. Procura "Tom Hanks", "filme" e "TMDB" nas telas e no código e não encontra nada.

**Entrega**
- Issue **`Entrega — Seu negócio no ar`** mencionando `@siriani`, com o link do commit, a URL no ar e os prints.
- README com a URL no ar (o subdomínio de sempre) e o diagrama de arquitetura atualizado.
- Migração e seed versionados.
- Prints: landing, listagem do recurso, 403 de papel sem permissão, bloqueio ao abrir registro de outro usuário, eventos de negócio no log, arquivo no MinIO e stack no Portainer com containers saudáveis.

### 3.2 Atividade 11: SaaS completo (planejada para 13/11/2026)

- **Modo de teste sempre.** Chaves nas variáveis da stack, nunca no repositório. Cartão nunca passa pelo servidor.
- **A assinatura é um estado mantido pela Stripe.** O banco guarda uma cópia **atualizada pelos webhooks**, não pelo retorno do navegador. Toda rota que depende do plano **consulta o banco a cada requisição**.
- **Webhooks**, sempre com assinatura validada e **sem efeito duplicado**:
  - `checkout.session.completed`: salva o customer e a subscription e muda para Pro.
  - `customer.subscription.updated`: atualiza plano e status.
  - `customer.subscription.deleted`: volta para Free.
  - `invoice.payment_failed`: marca inadimplência e avisa o usuário.

**Requisitos**
1. Planos **Free e Pro** (Team opcional) como produtos com preço recorrente mensal em R$; o Free pode custar R$ 0,00. Nomes, preços e limites seguem o README.
2. Rota de **checkout de assinatura** vinculada a um customer da Stripe **guardado no usuário**. Aqui o tenant é a oficina, então o customer fica em `assinaturas`, ligado à oficina e ao `usuario_id` do dono que assinou (seção 4.5). Explique essa adaptação no relatório.
3. Os **4 webhooks**.
4. Botão **"Gerenciar assinatura"** abrindo o Billing Portal, com cancelamento imediato configurado no painel para o teste.
5. **Limites por plano no backend**, com mensagem que explica o limite e como liberá-lo.
6. **Painel admin**, só para o papel admin: usuários por plano, assinaturas ativas, **MRR de teste** (soma mensal das assinaturas ativas) e últimos eventos do log.

**Roteiro do professor:**
1. Cria conta, que nasce Free.
2. Atinge o limite e vê a recusa.
3. Assina o Pro com o cartão **4242**.
4. Confirma que a mudança veio pelo webhook.
5. Cancela pelo portal e vê a volta ao Free.
6. Confere o painel admin.

**Entrega**
- Issue **`Entrega — SaaS completo`** mencionando `@siriani`, com o link do commit e os prints.
- `.env.example` só com os nomes das variáveis.
- Prints: assinatura concluída com 4242, dashboard da Stripe em modo de teste, webhook recebido, limite bloqueando no Free e painel admin.

### 3.3 P2: Relatório consolidado (entrega em 13/11/2026)

O PDF segue o template, nesta ordem:
1. Capa e sumário.
2. **1 Introdução** e **2 Metodologia**, com pelo menos 2 parágrafos cada, escritas pelo aluno.
3. **3 Arquitetura do SaaS**, com 3.1 Componentes, 3.2 Onde roda, 3.3 Fluxo de uma requisição, 3.4 Fluxo de assinatura, 3.5 Modelo de dados, 3.6 Segurança, 3.7 Observabilidade/CI/CD/Swagger e 3.8 IaaS/PaaS/SaaS. Descreve **o sistema que está no ar**.
4. **4 Quadro de entregas** (gerado automaticamente).
5. **5 Atividades realizadas**, com uma ficha por atividade, da 7 à 11.
6. **6 Considerações finais**.
7. **Declaração de autoria**.

**Evidência = link que abre + print com data e hora visíveis**; um sem o outro não vale.
- O print de commit mostra hash, data/hora e nome do repositório.
- Comando sugerido pelo professor: `git log -1 --date=format:"%d/%m/%Y %H:%M" --format="%h %ad"`.
- Da A9 em diante, a issue de entrega com `@siriani` também prova data e hora.
- A7 e A8 existem nos dois repositórios com o mesmo hash.

**Entrega da P2**
- Arquivo **`P2_ISW055_Nome_Sobrenome.pdf`** em `docs/` do repositório do produto.
- Link do PDF no README, que continua mencionando github.com/siriani.
- Issue **`Entrega — P2`** mencionando `@siriani`, com os links do PDF e do commit.
- **Critérios de avaliação:** arquitetura compatível com o sistema no ar; quadro completo, inclusive com as não entregues; fichas com evidência que abre; introdução e metodologia escritas pelo aluno; organização; honestidade.

### 3.4 Como o template Typst funciona (`docs/p2/P2_ISW055_template.typ`)

- **Dados do aluno:** ficam no topo, em `#let aluno`, `turma`, `produto`, `repositorio` e `data-relatorio`.
- **`#orientacao[...]`:** blocos cinza de instrução. **Todos devem ser apagados** no final, junto com as linhas-exemplo `[...]` das tabelas.
- **`#evidencia(legenda, arquivo: none)`:** é a figura. Troque `none` por `"prints/arquivo.png"`; o caminho é relativo ao `.typ`. A imagem entra com `width: 100%` e uma figura não quebra de página, então use prints **em paisagem do tamanho da janela** (1440×900), nunca uma página inteira rolada.
- **`#atividade(numero, titulo, descricao:, planejada:, realizada:, situacao:, evidencia:, url:)[corpo]`:** gera a ficha e alimenta o `registro` que monta o **Quadro de entregas** automaticamente.
  - `realizada` vem no formato `DD/MM/AAAA HH:MM`.
  - `situacao` é `entregue`, `entregue com atraso` ou `não entregue`.
- **Requisito de versão:** o template usa `context`, `state` e `table.header`, então exige **Typst 0.12 ou mais recente**. Mantenha **um único arquivo `.typ`**, para os caminhos das imagens não quebrarem.

---

## 4. Decisões de produto e arquitetura (já tomadas)

Siga estas decisões. Se o código mostrar um caminho melhor, justifique em `docs/execucao/DECISOES.md` antes de desviar.

### 4.1 Tenant e papéis

- **Tenant = oficina.** Toda tabela do domínio tem `oficina_id`.
- O `oficina_id` vem **sempre** do usuário autenticado, nunca de parâmetro, corpo ou URL.
- **Correção em relação ao README da A9:** o painel da A11 é da plataforma (mostra todas as oficinas e o MRR), então o dono da oficina não pode ser `admin`. Os papéis ficam assim:

| Papel | Quem é | O que pode |
|---|---|---|
| `admin` | administrador da plataforma (o João) | painel admin (planos, MRR, eventos de todas as oficinas) e leitura para suporte; **não cria nem edita OS** |
| `dono` | dono da oficina | tudo da própria oficina: equipe, código de convite, clientes, veículos, OS, exclusão e plano |
| `mecanico` | mecânico da oficina | abrir OS; ver e atualizar só as OS **atribuídas a ele** (itens, status até `pronta`, fotos); não exclui |
| `cliente` | cliente da oficina | ver só as OS dos **próprios veículos**; **aprovar orçamento**; nada mais |

- **Cadastro:**
  - "Sou dono" cria a oficina e o usuário `dono`.
  - "Sou mecânico" ou "Sou cliente" pede o **código de convite** da oficina, mostrado na tela Equipe do dono.
  - Isso deixa o professor criar duas contas de papéis diferentes sozinho.
- **Usuários antigos e Google:**
  - Os usuários antigos com papel `usuario` passam a `dono` sem oficina, e o primeiro acesso leva a "Crie sua oficina". O `admin` continua `admin`.
  - Login Google sem oficina segue o mesmo onboarding.
- **Atualizações de documentação:** a linha de papéis do mapa de reaproveitamento no README e o backlog (commit `docs:`).

### 4.2 Modelo de dados

| Onde | Tabela | Colunas principais |
|---|---|---|
| gateway (`alembic.ini`) | `oficinas` | id, nome, codigo_convite (único), criada_em |
| gateway | `clientes` | id, **oficina_id → oficinas**, usuario_id (nulo; id do auth), nome, telefone, email, criado_em |
| gateway | `veiculos` | id, **oficina_id → oficinas**, **cliente_id → clientes**, placa, marca, modelo, ano, único (oficina_id, placa) |
| gateway | `ordens_servico` | id, **oficina_id → oficinas**, **veiculo_id → veiculos**, mecanico_id (nulo; id do auth), criada_por, status, descricao, valor_total_centavos, criada_em, atualizada_em, excluida_em (exclusão lógica) |
| gateway | `itens_os` | id, **os_id → ordens_servico**, tipo (`servico`/`peca`), descricao, quantidade, valor_unitario_centavos |
| gateway | `anexos_os` | id, **os_id → ordens_servico**, chave_objeto, nome_original, tipo_mime, tamanho_bytes, enviado_por, criado_em |
| auth (`alembic-auth.ini`) | `usuarios` | + `oficina_id` (inteiro indexado, **sem FK entre serviços**: justifique no relatório); `role` ∈ {admin, dono, mecanico, cliente} |
| payment (`alembic-payment.ini`) | `assinaturas` | id, **oficina_id (único)**, usuario_id (quem assinou), stripe_customer_id, stripe_subscription_id, plano (`free`/`pro`), status, valor_mensal_centavos, moeda, periodo_fim, inadimplente, ultimo_evento_em (`event.created`), atualizado_em |
| payment | `processed_webhook_events` | já existe; a idempotência passa a ser gravada **na mesma transação** do efeito |

- **Dinheiro:** sempre em centavos (inteiro).
- **Cadastro do dono:** quem orquestra é o gateway, numa rota `POST /api/cadastro`. Ele cria a oficina, chama o registro interno do auth-service com `oficina_id` e `role`, e desfaz a oficina se o auth falhar.

### 4.3 Ordem de serviço

- **Status:** `aberta` → `orcamento_aprovado` → `em_servico` → `pronta` → `entregue`. `cancelada` só pelo dono e antes de `entregue`. Transição inválida responde **409**.
- **`orcamento_aprovado`:** só o cliente dono do veículo ou o dono da oficina.
- **`entregue`:** só o dono.
- **Total da OS:** soma dos itens.
- **Exclusão:** é lógica (`excluida_em`) e **não devolve cota do plano**.

### 4.4 Planos e limites (do README)

- **Free:**
  - **20 OS por mês.** Conta as OS criadas no mês corrente no fuso America/Sao_Paulo, incluindo as excluídas.
  - **1 mecânico.**
  - **3 anexos por OS.**
  - **Histórico do veículo de 30 dias:** é opcional. Se não implementar, corrija a tabela do README para refletir a realidade.
- **Pro (R$ 49/mês):** sem esses limites.
- **Resposta ao limite:**
  - HTTP **402** com JSON `{erro, codigo: "limite_plano", limite, uso, plano, como_liberar: "Assine o Pro (R$ 49/mês) em Plano e assinatura"}`.
  - Evento `plano.limite_atingido` no log.
  - Na tela, um banner com o botão "Assinar Pro".
- Os limites ficam numa constante (`PLANOS = {...}`) e são testados.

### 4.5 Assinatura: fonte da verdade

- **Rotas:** reaproveite as que já existem no gateway, `POST /api/payment/checkout`, `POST /api/payment/portal` e `POST /api/payment/webhook`. O endpoint do webhook na Stripe já aponta para esta última desde a A7. Só renomeie se houver motivo, e então documente.
- **Checkout** (`POST /api/payment/checkout`, só para o dono):
  - Cria ou reutiliza o customer da oficina e guarda `stripe_customer_id` em `assinaturas`.
  - Chama `mode="subscription"` com `client_reference_id=oficina_id` e metadata `{oficina_id, usuario_id}`.
  - O preço Pro vem de `STRIPE_PRICE_ID`: mesma variável, valor novo no Portainer.
- **Retorno do navegador:** mantenha o formato atual de `STRIPE_SUCCESS_URL`/`STRIPE_CANCEL_URL` (`/?payment=success`) para não mexer no Portainer. O Angular redireciona para "Plano e assinatura", mostra "processando…" e consulta o plano. **O retorno não muda o plano.**
- **Webhook:**
  - Valida a assinatura e rejeita com 400 se for inválida.
  - Numa única transação, grava o `event.id` em `processed_webhook_events` e aplica o efeito.
  - Se o efeito falhar, faz rollback e responde 500, para a Stripe reenviar.
  - Evento repetido responde 200 sem efeito.
  - Eventos fora de ordem: ignore os que tiverem `event.created` menor que `ultimo_evento_em`.
  - Efeito de cada evento:
    - `checkout.session.completed`: grava customer e subscription, `plano=pro` e `status`.
    - `customer.subscription.updated`: atualiza `status`, `periodo_fim`, `valor_mensal_centavos` e o plano pelo price.
    - `customer.subscription.deleted`: `plano=free`, `status=canceled`.
    - `invoice.payment_failed`: `inadimplente=true` e banner "pagamento falhou, atualize o cartão" para o dono.
- **Decisão de limite:** cada requisição lê `assinaturas` no banco. O gateway consulta um endpoint interno do payment-service que lê o banco, **sem chamar a Stripe e sem cache Redis**.
- **Portal** (`POST /api/payment/portal`, só para o dono): abre `billing_portal.Session` do customer da oficina.
- **Painel admin** (`GET /api/admin/painel`, só para `admin`):
  - Oficinas e usuários por plano.
  - Assinaturas ativas.
  - **MRR de teste** = soma de `valor_mensal_centavos` das assinaturas `active` ou `trialing`.
  - Últimos eventos do log-service.
  - O painel `/api/admin/infra/*` existente continua.

### 4.6 Eventos de negócio (log-service)

- **Eventos:**
  - `oficina.criada`, `membro.entrou`, `cliente.criado`, `veiculo.criado`
  - `os.aberta`, `os.editada`, `os.item_adicionado`, `os.status_alterado`, `os.orcamento_aprovado`, `os.entregue`, `os.cancelada`, `os.excluida`
  - `anexo.enviado`, `acesso_negado` (403/404 do domínio), `plano.limite_atingido`
  - `assinatura.ativada`, `assinatura.atualizada`, `assinatura.cancelada`, `pagamento.falhou`
- **Campos:** usuario_id, papel, oficina_id, recurso e id, IP e data/hora. Sem dados pessoais sensíveis no detalhe.
- **Continuam como hoje:** login, logout e erro.
- **Painel de auditoria:** filtro por tipo de evento e por oficina.

### 4.7 Arquivos (MinIO)

- **O que se envia:** fotos da entrada do veículo, das peças trocadas e comprovantes, ligadas à OS. Chave `os/<oficina_id>/<os_id>/<uuid>.<ext>`; o banco guarda só a chave.
- **Validação:** PNG, JPEG ou WEBP pelo conteúdo (bytes mágicos), até 5 MB.
- **Leitura:** pela rota do gateway, **com checagem de papel e oficina**.
- **Os anexos de OS não podem ficar públicos.** Hoje o bucket tem política de leitura pública para avatares. Restrinja a política ao prefixo dos avatares ou use um bucket privado separado, o que for menos invasivo depois de ler `auth_service/app.py`, e registre a decisão.

### 4.8 Frontend (Angular)

- **Estrutura:**
  - Renomeie `frontend/front-tom-hanks` para `frontend/oficinaos-web` (projeto `oficinaos-web`).
  - Mude o build para **estático (CSR)**, gerando `index.html` em `dist/oficinaos-web/browser`.
  - Crie `scripts/build_frontend.sh`, que limpa `backend/static` e copia o build novo, eliminando os bundles antigos.
  - Introduza o **Angular Router** com componentes standalone. O `serve_frontend` do Flask já devolve `index.html` para rotas profundas.
- **Rotas:**
  - Públicas: `/` (landing), `/entrar`, `/cadastro`, `/recuperar-senha`.
  - Autenticadas: `/app/os`, `/app/os/nova`, `/app/os/:id`, `/app/os/:id/editar`, `/app/clientes`, `/app/veiculos`, `/app/equipe`, `/app/plano`, `/app/perfil`, `/app/auditoria` (só dono e admin), `/admin` (só admin).
- **Landing:**
  - Proposta de valor: "Pare de perder serviço no caderno".
  - Três benefícios: OS com status, histórico do veículo com fotos e orçamento aprovado pelo cliente.
  - Planos Free × Pro e o botão **"Criar conta grátis"**.
- **Linguagem do negócio em todas as telas:** "Abrir ordem de serviço", "Aprovar orçamento", "Entregar veículo".

### 4.9 O que sai (Tom Hanks, filmes, TMDB)

- **Gateway:**
  - As rotas `/api/catalog`, `/api/favorites*`, `/api/comments*` e `/api/premium/*` de filmes.
  - Os modelos `Favorite` e `Comment` e os testes ligados a eles.
  - As specs Swagger dessas rotas e o `openapi.*`, que deve ser regenerado.
- **Configuração:**
  - `TMDB_API_KEY` e `TMDB_LANGUAGE` saem do código, do compose e do `.env.example`; o João tira também da stack.
- **Nomes e textos legados:**
  - A rede `tomhanks-net` vira `oficinaos-net`, com o cuidado da seção 8.
  - Os padrões `tomhanks-avatars` e `noreply@tomhanks.local` são trocados.
  - Os títulos do dashboard do Grafana são atualizados.
  - Os scripts `demo_*.sh` são atualizados ou removidos.
  - Comentários do CI e textos e títulos do frontend também saem.
- **O que fica:** os documentos históricos `docs/P1_*.pdf`, `docs/backlog-issues.md` e `docs/entrega-ativ9.md`. No README e no `DOCUMENTACAO.md`, a origem do projeto aparece **só** numa seção "Histórico do projeto", com link para o `tomhanks`.
- **Verificação**, que deve sair vazia:

```bash
git grep -niE "tom ?hanks|tomhanks|tmdb|filme|movie" -- . \
  ':!docs/' ':!README.md' ':!DOCUMENTACAO.md' ':!backend/migrations/versions/0001_*'
grep -niE "tom ?hanks|tmdb|filme" README.md DOCUMENTACAO.md   # só dentro de "Histórico do projeto"
```

### 4.10 Migrações sem quebrar o banco da turma

- O banco de produção já está na revisão `0001_initial` do gateway.
- **Não apague nem renomeie essa revisão.** Transforme o conteúdo de `upgrade()` em um *baseline* neutro, com um comentário explicando que o histórico antigo está no git. Assim um banco novo não cria mais tabelas de filmes.
- Crie a `0002_dominio_oficina` (`down_revision = '0001_initial'`), que faz `DROP TABLE IF EXISTS` de `comentarios` e `favoritos` e cria as tabelas do domínio.
- **O `DROP` roda no banco da turma assim que o deploy acontece** (seção 1), então a confirmação do João vem **antes do push** que leva essa migração. Ofereça antes um `mysqldump` dessas duas tabelas.
- Exporte o SQL versionado para o professor:
  - `db/001_dominio.sql`, gerado por Alembic em modo offline (`--sql`), com o script `scripts/export_sql.sh`.
  - `db/002_seed.sql`, idempotente (`INSERT IGNORE`/`ON DUPLICATE KEY`), com pelo menos 2 oficinas, 3 clientes, 4 veículos e 5 OS fictícias. O seed **não cria login nem senha**.
  - `db/README.md`, explicando como recriar o banco.
- Faça as migrações equivalentes no auth (`0003_papeis_oficina`, depois de `0002_google_oauth`: papéis + `oficina_id`) e no payment (`0002_assinaturas`, depois de `0001_payment_init`, com migração do legado `stripe_customers`).
- Como auth e payment também chamam `create_all`, os modelos e as migrações devem bater exatamente, ou o banco fica com colunas diferentes do esperado. Teste `alembic upgrade head` dos três serviços num MariaDB vazio **e** num MariaDB com o esquema antigo (restaure o esquema antigo checando o commit `96b2297`).

---

## 5. Fase 0: Preparação (sem mudar comportamento)

**5.1 Perguntas ao João, numa única rodada no início:**
1. Qual a **URL pública** do sistema (o subdomínio de sempre) e o **nome da stack** no Portainer?
2. O motivo do atraso da **A8** (se confirmado) e da **A10**, em uma ou duas frases, para as fichas.
3. Você tem os **prints originais** da entrega da A7 (checkout concluído, usuário premium) e da A9 (aba Commits, issues)? Em que pasta?
4. A Stripe está em modo de teste com acesso ao painel? Você prefere configurar produtos, portal e webhook você mesmo (recomendado) ou autoriza o uso do `stripe` CLI com `stripe login`?
5. Confirma o nome **João Victor Serrano**, a turma **161_SIST. INTELIGENTES_N** e o arquivo **`P2_ISW055_Joao_Serrano.pdf`**?

**5.2 Ferramentas** (verifique com `--version` e instale o que faltar, sem apagar nada):

| Ferramenta | Uso | Como instalar |
|---|---|---|
| Python 3.12 + venv | serviços e testes | `python -m venv venv && pip install -r requirements.txt -r auth_service/requirements.txt -r log_service/requirements.txt -r payment_service/requirements.txt pytest` |
| Node 22 + npm | build do Angular | `cd frontend/... && npm ci` |
| Docker + Compose | stack local | já usado no projeto |
| Typst ≥ 0.12 | relatório | binário oficial (github.com/typst/typst/releases), `cargo install --locked typst-cli`, `brew install typst`, `winget install Typst.Typst`, ou, como fallback, `pip install typst` (`python -c "import typst; typst.compile(...)"`) |
| Playwright (Python) | navegador e prints | `pip install playwright && python -m playwright install chromium` |
| mermaid-cli | diagramas | `npx -y @mermaid-js/mermaid-cli -V` |
| poppler-utils | conferir o PDF | `pdftotext`, `pdftoppm`, `pdfinfo` |
| gh | issues e conferência | `gh auth status` (a autenticação é do João) |
| stripe CLI (opcional) | webhooks locais | `stripe listen --forward-to localhost:8080/api/payment/webhook` |

**5.3 Ambiente local**
- Crie o `docker-compose.dev.yml` (override) com um serviço `mariadb:11` local e as variáveis de banco apontando para ele. **Nunca use o banco da turma para desenvolver.**
- Gere o `.env` local a partir do `.env.example`, com valores fictícios ou de teste.
- O João coloca as chaves `sk_test_`/`pk_test_` dele no `.env` local se quiser testar o checkout localmente.
- Suba com `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build`.

**5.4 Linha de base**
- Rode `pytest tests/ -v` e guarde a saída.
- Liste com `git grep` as ocorrências legadas da seção 4.9.
- Confira em `start.sh` se as migrações rodam no start dos containers.

**5.5 Primeiros commits** (sem código de produto):
- `docs: atualiza CLAUDE.md para as atividades 10, 11 e P2`. Inclui a nova fase, os comandos de build do frontend, Typst e Playwright, a remoção autorizada do legado e as regras desta seção 2.
- `docs: plano de execução e registro de decisões` (`docs/execucao/EXECUCAO.md` e `DECISOES.md`).
- `chore(dev): compose de desenvolvimento com MariaDB local`.
- `chore: ignora artefatos de evidência e do navegador`. Acrescenta ao `.gitignore`: `.env.evidencias`, `.evidencias/`, `playwright/.auth/`, `*.storage-state.json`, `frontend/oficinaos-web/node_modules/`, `frontend/oficinaos-web/dist/`, `frontend/oficinaos-web/.angular/`.

---

## 6. Fase 1: Atividade 10 (tarefas pequenas, testes antes e um commit cada)

Em toda tarefa: (1) escreva o teste que falha; (2) implemente o mínimo; (3) `pytest tests/ -v` verde, incluindo a paridade do Swagger; (4) commit. Siga os padrões de mock e fixtures dos testes existentes. Para o domínio, crie testes novos como `tests/test_oficina_api.py`, `tests/test_papeis.py` e `tests/test_anexos.py`.

| # | Tarefa | Aceite (provado por teste ou comando) | Commit sugerido |
|---|---|---|---|
| T10.1 | Migrações do gateway: baseline neutro + `0002_dominio_oficina` | `alembic upgrade head` limpo no MariaDB local; FKs e índice único (oficina, placa) criados | `feat(db): tabelas do domínio de oficina com migração Alembic` |
| T10.2 | `db/001_dominio.sql`, `db/002_seed.sql`, `db/README.md`, `scripts/export_sql.sh` | o SQL aplica num banco vazio; o seed reaplica sem erro | `feat(db): exporta migração e seed SQL versionados` |
| T10.3 | Modelos SQLAlchemy + helper de escopo por oficina (toda consulta passa por ele) | teste: consulta sem escopo não existe nas rotas; registro de outra oficina → `None` | `feat(dominio): modelos e escopo obrigatório por oficina` |
| T10.4 | Auth: papéis `admin/dono/mecanico/cliente`, `oficina_id` e migração de papéis antigos | papel inválido → 400; `/me` devolve papel e oficina | `feat(auth): papéis do negócio e vínculo com a oficina` |
| T10.5 | Cadastro orquestrado (`/api/cadastro`) + código de convite (dono gera; mecânico e cliente entram) | dono cria a oficina; código inválido → 400; 2º mecânico no Free → 402 (liga com a A11, pode entrar já) | `feat(auth): cadastro de dono e entrada por código de convite` |
| T10.6 | Decorador `require_roles(*papeis)` + contexto da oficina no gateway | 401 sem login; 403 com papel errado, chamando a API direto | `feat(gateway): autorização por papel e contexto da oficina` |
| T10.7 | CRUD de clientes e veículos (dono) | cliente de outra oficina → 404; mecânico criando cliente → 403 | `feat(api): clientes e veículos da oficina` |
| T10.8 | CRUD de OS + itens + transições de status | listar, criar, detalhar, editar e excluir (lógica); transição inválida → 409; mecânico excluindo → 403; OS de outra oficina → 404; mecânico em OS não atribuída → 404; cliente só vê as próprias | `feat(api): ordens de serviço com itens e status` |
| T10.9 | Eventos de negócio + `acesso_negado` no log-service | o teste verifica a chamada ao log com usuário, oficina e recurso | `feat(log): eventos de negócio das ordens de serviço` |
| T10.10 | Anexos da OS no MinIO (upload, lista, leitura protegida) | tipo ou tamanho inválido → 400; outra oficina → 404; política sem leitura pública para `os/` | `feat(anexos): fotos e comprovantes da OS no MinIO` |
| T10.11 | Swagger dos endpoints novos + `python scripts/generate_openapi.py` | teste de paridade verde | `docs(api): Swagger das rotas do domínio` |
| T10.12 | Remoção do legado do backend (seção 4.9), em commits separados por área | `git grep` do legado vazio no backend; rotas antigas → 404 | `refactor!: remove o catálogo de filmes e a integração TMDB` (com `BREAKING CHANGE:`) |
| T10.13 | Frontend: renomear pasta, build estático, Router, landing, cadastro, telas de OS, clientes, veículos, equipe e auditoria | `npm run build` sem erro; fluxo completo pela interface no ambiente local | vários: `refactor(web): renomeia o frontend para oficinaos-web`, `build(web): build estático CSR`, `feat(web): landing page pública`, `feat(web): telas de ordens de serviço`… |
| T10.14 | `scripts/build_frontend.sh` + `backend/static` limpo e atualizado | só um bundle atual em `backend/static` | `build(frontend): publica o build do OficinaOS em backend/static` |
| T10.15 | Compose: `mem_limit: 1g` em cada serviço (se o João confirmar), rede `oficinaos-net` e padrões sem "tomhanks" | `docker compose config` válido; stack local saudável | `build(compose): limites de memória e nomes do OficinaOS` |
| T10.16 | Documentação: README (URL no ar, diagrama Mermaid atualizado, papéis, como recriar o banco), `DOCUMENTACAO.md` do OficinaOS e `.env.example` sem TMDB | o README continua mencionando github.com/siriani | `docs: README e documentação do OficinaOS` |
| T10.17 | `scripts/cenarios/ativ10.py --base-url URL`, que roda o cenário do professor com `requests` e imprime PASS/FAIL por passo | todos os passos PASS no ambiente local | `test(e2e): cenário de aceite da atividade 10` |

**Ponto de checagem A10:** com tudo verde localmente, mostre ao João o resumo, o `git log --oneline` do trecho e a saída do cenário, e **peça autorização para o push**. Avise com clareza que esse push dispara o deploy e roda a migração que apaga `favoritos` e `comentarios` no banco da turma; ofereça o `mysqldump` antes. Depois vá para a seção 8 (deploy). Os passos do João no Portainer e no GitHub podem ser feitos antes do push.

---

## 7. Fase 2: Atividade 11

| # | Tarefa | Aceite | Commit sugerido |
|---|---|---|---|
| T11.1 | Migração `assinaturas` no payment-service + migração do legado `stripe_customers` | upgrade limpo; a oficina sem linha é tratada como Free | `feat(payment): tabela de assinaturas por oficina` |
| T11.2 | Webhooks: os 4 eventos, transação única, idempotência, fora de ordem, assinatura inválida → 400 | testes com payload assinado pelo segredo de teste: evento repetido não duplica; `deleted` volta ao Free; `payment_failed` marca inadimplência; efeito que falha → 500 e o evento não fica marcado | `feat(payment): webhooks de assinatura idempotentes` |
| T11.3 | Checkout de assinatura por oficina (só dono) | mecânico ou cliente → 403; o customer é reutilizado; metadata e `client_reference_id` presentes | `feat(payment): checkout de assinatura da oficina` |
| T11.4 | Portal do cliente (só dono) | oficina sem customer → 409 com mensagem | `feat(payment): portal do cliente Stripe` |
| T11.5 | Endpoint interno de plano (lê o banco) + limites no gateway (OS por mês, mecânicos, anexos) → 402 | 21ª OS no Free → 402 com mensagem; no Pro passa; o teste garante que nenhuma chamada à Stripe acontece na decisão | `feat(planos): limites do Free aplicados na API` |
| T11.6 | Remover o uso do entitlement legado por `google_id` e o cache Redis nas decisões de plano | `git grep google_id` no payment só onde ainda for necessário | `refactor(payment): plano lido do banco a cada requisição` |
| T11.7 | Painel admin (API + tela `/admin`): oficinas e usuários por plano, assinaturas ativas, MRR de teste e últimos eventos | não-admin → 403; MRR = soma correta no teste | `feat(admin): painel com planos, assinaturas e MRR de teste` |
| T11.8 | Tela "Plano e assinatura": plano atual, uso (x/20), "Assinar Pro", "Gerenciar assinatura", "processando…" após o checkout, banners de limite e de inadimplência | fluxo local com `stripe listen` | `feat(web): plano, assinatura e avisos de limite` |
| T11.9 | `.env.example` (só nomes), README (planos, fluxo de assinatura, como testar webhook) e Swagger das rotas novas | paridade verde; nenhum valor real no `.env.example` | `docs: planos, assinatura e variáveis da atividade 11` |
| T11.10 | `scripts/cenarios/ativ11.py`, com os passos que não exigem cartão, + `scripts/evidencias/checkout.py` (Playwright) para o checkout 4242 | todos PASS localmente | `test(e2e): cenário de aceite da atividade 11` |

**Ponto de checagem A11:** o mesmo da A10. Mostre o resultado e peça autorização para o push. Depois vá para a seção 8.

---

## 8. Fase 3: Deploy e verificação no ar (passos do João e seus)

Prepare para o João o checklist `docs/execucao/DEPLOY.md` com estes itens e acompanhe item a item.

**GitHub (João)**
- Criar no OficinaOS os secrets `PORTAINER_WEBHOOK_URL` e `DEPLOY_HEALTH_URL`, que não vieram no mirror.
- Conferir se o Actions está habilitado.
- Conferir a visibilidade e o acesso dos pacotes `oficinaos-*` no GHCR.

**Portainer (João; mesma stack, sem criar outra)**
- Trocar o repositório da stack para `https://github.com/JoaoVSerrano/OficinaOS`. Se a versão do Portainer não permitir editar a URL, **pare e avise**: nada de stack nova sem falar com o professor.
- Variáveis:
  - Remover `TMDB_API_KEY` e `TMDB_LANGUAGE`.
  - Atualizar `STRIPE_PRICE_ID` para o preço Pro de R$ 49/mês.
  - Se você mudou o bucket ou a rede, atualizar `MINIO_BUCKET_NAME` e as demais. O resto fica igual.
- **Rede renomeada:** a subnet `10.201.0.0/24` é fixa. Se a rede antiga ainda existir, o redeploy falha com "Pool overlaps". O João remove a rede antiga logo depois de parar a stack; descreva o passo exato no checklist.
- **Migração destrutiva:** o `DROP` das tabelas de filmes roda sozinho quando o container novo sobe (seção 4.10). A confirmação do João, e o `mysqldump` se ele quiser, vêm **antes do push** que leva a `0002_dominio_oficina`.
- Fazer pull + redeploy e conferir **todos os containers saudáveis**.

**Stripe, modo de teste (João, ou você com `stripe login` autorizado)**
- Produtos **Free (R$ 0,00/mês)** e **Pro (R$ 49,00/mês, BRL, recorrente mensal)**.
- **Customer Portal**: permitir cancelamento **imediato** e atualização do cartão.
- **Webhook** em `https://<subdominio>/api/payment/webhook` com os eventos `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted` e `invoice.payment_failed`. Se o endpoint for novo, o segredo de assinatura vai para `STRIPE_WEBHOOK_SECRET` no Portainer.

**Verificação no ar (você)**
- `gh run watch` até o CI ficar verde.
- `curl -fsS https://<subdominio>/health`.
- `python scripts/cenarios/ativ10.py --base-url https://<subdominio>` e depois `ativ11.py`.
- Guarde as saídas em `docs/execucao/verificacao-<data>.txt`, sem dados sensíveis.

---

## 9. Fase 4: Evidências com navegador (Playwright)

**9.1 Princípios**
- Prints do **sistema no ar** (a URL do João), tirados com Chromium real via Playwright.
- O script fica versionado em `scripts/evidencias/capturar.py`. As senhas das contas de demonstração vão em `.env.evidencias`, que é ignorado pelo git.
- As contas são criadas pela própria interface ou API. Esse uso também gera os eventos de log que aparecem nos prints.
- Contexto: `viewport 1440×900`, `device_scale_factor 1.5`, `locale "pt-BR"`, `timezone_id "America/Sao_Paulo"`.
- Print do tamanho da janela, **nunca página inteira**: role até o ponto certo ou use `clip`.
- PNGs em `docs/p2/prints/`, nomeados `aNN-XX-descricao.png`, otimizados (`oxipng`/`pngquant`, se houver).
- Na legenda vai a data e a hora reais da captura. **Nunca desenhe nem sobreponha nada na imagem.**
- **Páginas com login de terceiros** (painel da Stripe, Portainer, console do MinIO):
  - Abra o navegador **visível** (`headless=False`) com perfil persistente em `.evidencias/perfil/` (ignorado pelo git).
  - Peça ao João que faça o login ele mesmo. Nunca digite as senhas dele.
  - Espere com `wait_for_url`/`wait_for_selector` e timeout longo, depois capture só a área sem segredos.
  - Se não houver interface gráfica, o João tira esses prints manualmente com os nomes da tabela 9.3.
- **Datas no GitHub:** commits e issues públicos não precisam de login. O GitHub mostra datas relativas, e o professor exige data **e hora** visíveis. Faça assim:
  - Configure o próprio componente `<relative-time>` do GitHub para exibir o `datetime` que ele já contém, por exemplo com o atributo `format="datetime"`, **sem alterar o valor**.
  - Declare esse procedimento na Metodologia.
  - Se não funcionar na versão atual do GitHub, o João tira esses prints com o tooltip de data aberto.
  - Em todos os casos, a ficha também traz a saída real do `git log` correspondente.

Esqueleto de referência:

```python
from playwright.sync_api import sync_playwright

OPCOES = dict(viewport={"width": 1440, "height": 900}, device_scale_factor=1.5,
              locale="pt-BR", timezone_id="America/Sao_Paulo")

def datas_absolutas_github(page):
    # Usa o componente do próprio GitHub para mostrar o datetime que ele já contém.
    page.evaluate("""() => document.querySelectorAll('relative-time')
        .forEach(el => el.setAttribute('format', 'datetime'))""")

def capturar(page, url, arquivo, preparar=None):
    page.goto(url, wait_until="load")
    page.wait_for_timeout(1500)
    if preparar:
        preparar(page)
    page.screenshot(path=f"docs/p2/prints/{arquivo}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_context(**OPCOES).new_page()
    capturar(page, "https://github.com/JoaoVSerrano/OficinaOS/commits/main",
             "a09-02-aba-commits.png", datas_absolutas_github)
    browser.close()
```

**9.2 Status code visível:** o navegador não mostra o status HTTP. Para os prints de 403 e 404, use o **Swagger UI do próprio sistema** (`/docs`), que já existe. Entre com a conta certa, use "Try it out" e "Execute" e capture a seção "Server response", que mostra o código, o corpo e a URL. Complemente com a tela do app mostrando "Ordem de serviço não encontrada" ao trocar o ID na URL.

**9.3 Lista de prints**

| Arquivo | O que mostrar | Como |
|---|---|---|
| `a07-01-commit.png` | commit da A7 no `tomhanks` (hash, data/hora, repositório) | GitHub, automático |
| `a07-02-resultado.png` | print original do checkout ou do premium da A7; se não houver, a visão do GitHub no commit `b4639dd` | João ou automático, com legenda honesta |
| `a08-01-commit.png` | commit `2061f81` (ou o real da A8) | automático |
| `a08-02-documentacao.png` | `DOCUMENTACAO.md` renderizado no commit da A8 | automático |
| `a09-01-issue.png` | issue `Entrega — Fork e plano de negócio` com data e hora | automático |
| `a09-02-aba-commits.png` | aba Commits do OficinaOS com os commits antigos e `d8abb36` | automático (ou o print original do João) |
| `a09-03-issues.png` | lista de issues do backlog | automático |
| `a10-01-landing.png` | landing sem login | automático |
| `a10-02-lista-os.png` | listagem de OS (dono) | automático |
| `a10-03-detalhe-os-foto.png` | detalhe da OS com a foto enviada | automático |
| `a10-04-403-papel.png` | Swagger: mecânico tentando excluir OS → 403 | automático |
| `a10-05-bloqueio-outro.png` | outra oficina abrindo o ID da 1ª → 404 (Swagger) e a tela de "não encontrada" | automático |
| `a10-06-log-eventos.png` | auditoria como admin: eventos `os.*` com quem e quando | automático |
| `a10-07-minio.png` | o objeto em `os/...` no console do MinIO (João faz login); alternativa: a foto servida pelo app + saída de `mc ls` na ficha | assistido |
| `a10-08-portainer.png` | stack com os containers saudáveis, **sem a aba de variáveis** | assistido |
| `a10-09-issue.png`, `a10-10-commit.png` | issue de entrega e commit da A10 | automático |
| `a11-01-limite-free.png` | 21ª OS recusada com a mensagem do plano | automático |
| `a11-02-checkout-4242.png` | Checkout da Stripe em modo de teste preenchido com 4242 | automático (cartão de teste público) |
| `a11-03-pro-ativo.png` | app mostrando o plano Pro depois do webhook | automático |
| `a11-04-stripe-dashboard.png` | assinaturas no painel da Stripe com o selo de modo de teste | assistido |
| `a11-05-webhook.png` | entregas do webhook com resposta 200 (Stripe) e o evento `assinatura.ativada` no log | assistido + automático |
| `a11-06-portal-cancelar.png` | cancelamento imediato no portal | automático ou assistido |
| `a11-07-voltou-free.png` | app de volta ao Free | automático |
| `a11-08-painel-admin.png` | painel admin com planos, assinaturas ativas, MRR de teste e eventos | automático |
| `a11-09-issue.png`, `a11-10-commit.png` | issue de entrega e commit da A11 | automático |
| `readme-siriani.png` | README do OficinaOS com a menção a github.com/siriani | automático |
| `diagrama-*.png` | arquitetura, requisição, assinatura e modelo de dados (seção 10.3) | mermaid-cli |

Dados do cartão de teste: `4242 4242 4242 4242`, validade futura (ex.: `12/34`), CVC `123` e nome "Teste OficinaOS". Ele só funciona em modo de teste.

**Commit dos prints:** `docs(p2): prints de evidência das atividades 7 a 11`. Faça commits separados à medida que os prints ficam prontos.

---

## 10. Fase 5: Relatório P2 em Typst

**10.1 Arquivos**
- `docs/p2/P2_ISW055_template.typ` é o original, intocado.
- `docs/p2/P2_ISW055_Joao_Serrano.typ` é a cópia preenchida.
- `docs/p2/prints/` guarda os prints e `docs/p2/diagramas/*.mmd` as fontes Mermaid.
- A saída é **`docs/P2_ISW055_Joao_Serrano.pdf`**.

**10.2 Dados:** `aluno = "João Victor Serrano"`, `turma = "161_SIST. INTELIGENTES_N"`, `produto = "OficinaOS"`, `repositorio = "https://github.com/JoaoVSerrano/OficinaOS"` e `data-relatorio` igual à data real da entrega (até 13/11/2026). Confirme na Fase 0.

**10.3 Diagramas**
- Escreva em Mermaid, versionado, a partir do que **está no ar**:
  - `arquitetura.mmd`: o app público pelo domínio; o auth, o log + Redis e o payment na rede interna; o MariaDB externo; o MinIO; a Stripe com checkout, portal e webhook; Prometheus e Grafana.
  - `fluxo-requisicao.mmd`: sequência de "mecânico muda o status da OS para pronta".
  - `fluxo-assinatura.mmd`: sequência de checkout → Stripe → webhook → `assinaturas` → limite liberado, com o cancelamento pelo portal.
  - `modelo-dados.mmd`: `erDiagram` das tabelas da seção 4.2.
- Renderize em PNG a partir da raiz do repositório com `npx -y @mermaid-js/mermaid-cli -i docs/p2/diagramas/X.mmd -o docs/p2/prints/diagrama-X.png -s 3 -b white`. Evite SVG com `foreignObject`, porque o Typst não renderiza esse texto.
- Use o mesmo diagrama de arquitetura no README.

**10.4 Conteúdo por seção** (fatos do repositório, nada de projeto ideal)
- **Introdução e Metodologia:**
  - **Rascunho** em primeira pessoa, com pelo menos 2 parágrafos cada, para o João revisar e **reescrever com as palavras dele**: o critério da P2 pede que sejam do aluno.
  - A Metodologia diz como os prints foram capturados (Playwright, data e hora reais, procedimento das datas do GitHub) e que o Claude Code foi usado como ferramenta de apoio no código e na montagem do relatório.
- **3.1 Componentes:**
  - Complete a tabela com tecnologia e imagem reais: `ghcr.io/joaovserrano/oficinaos-*`, `redis:7-alpine`, `cgr.dev/chainguard/minio`, Flask, Gunicorn e Angular, e o que é público e o que é interno.
  - Acrescente as linhas do `payment-service`, do Prometheus e do Grafana.
- **3.2 Onde roda:** VM Proxmox (Ubuntu + Docker), nome da stack, repositório de onde ela puxa, containers e limites, **nomes** das variáveis (a lista do `.env.example`, sem valores) e a URL pública.
- **3.3 a 3.5:** os diagramas mais um texto curto. No 3.4, diga como o webhook é validado, o que acontece com evento repetido ou fora de ordem e como funciona o cancelamento.
- **3.6 Segurança:** tabela de ações × `admin`/`dono`/`mecanico`/`cliente` (acrescente uma coluna ao exemplo), escopo por oficina em todas as consultas, 404 para registro de outra oficina e segredos só na stack, com `.env.example` só de nomes.
- **3.7:** Swagger com paridade testada, CI/CD (testes → GHCR → webhook do Portainer → smoke em `/health`), `/health` com readiness real, `/metrics` e Grafana.
- **3.8:**
  - IaaS: a VM, a rede e o disco, geridos pela Fatec/professor.
  - PaaS: Docker + Portainer, MariaDB, Redis e MinIO, com a gestão dividida entre você e o professor; explique.
  - SaaS: o OficinaOS para as oficinas e os SaaS consumidos (Stripe, GitHub).
- **Considerações finais:** de 1 a 3 parágrafos, rascunho para o João revisar.
- **Declaração de autoria:** mantenha. O João assina, se quiser, numa versão posterior do mesmo arquivo (o que conta é o primeiro commit).

**10.5 Fichas**
- Obtenha cada data com `git log -1 --date=format:"%d/%m/%Y %H:%M" --format="%h %ad %s" <hash>` e, para as issues, com `gh issue view <n> --json title,createdAt,url`, convertendo para America/Sao_Paulo.
- Em cada ficha:
  - `url` = link direto da evidência (o commit no `tomhanks` para A7 e A8; a issue de entrega da A9 em diante).
  - `situacao` = comparação honesta entre planejada e realizada.
  - Corpo com "O que foi feito" (citando os commits principais), as figuras da tabela 9.3, a saída do `git log` em bloco de código e "Dificuldades e como foram resolvidas", usando as justificativas de atraso informadas pelo João.
- A ficha da A10 traz os 7 prints exigidos e mais o da issue; a da A11, os 5 exigidos e mais o da issue.

**10.6 Limpeza obrigatória**
- Apague todas as chamadas `#orientacao[...]` e as linhas-exemplo `[...]`.
- Substitua todos os "Escreva aqui…" e "DD/MM/AAAA HH:MM".
- Nenhum `arquivo: none` deve sobrar.

**10.7 Compilar e conferir**

```bash
# fonte limpa: nenhum bloco de orientação, linha-exemplo ou figura sem arquivo
grep -nE '#orientacao\[|\[\.\.\.\]|#evidencia\(\[[^]]*\]\)' docs/p2/P2_ISW055_Joao_Serrano.typ || echo "OK: fonte limpa"

typst compile docs/p2/P2_ISW055_Joao_Serrano.typ docs/P2_ISW055_Joao_Serrano.pdf
pdfinfo docs/P2_ISW055_Joao_Serrano.pdf
pdftotext docs/P2_ISW055_Joao_Serrano.pdf - | grep -nE "cole o print|Escreva aqui|Descreva aqui|Descreva em um ou dois|Um parágrafo curto|DD/MM/AAAA|SEU-USUARIO|REPOSITORIO-ANTIGO|NOME-DO-PRODUTO|Nome Completo|O que escrever aqui" || echo "OK: sem marcas do template"
mkdir -p .evidencias/paginas && pdftoppm -r 60 -png docs/P2_ISW055_Joao_Serrano.pdf .evidencias/paginas/p
```

- Abra as imagens das páginas e confira capa, sumário, quadro de entregas, figuras legíveis (nenhuma cortada ou estourando a página) e numeração.
- Corrija os avisos do Typst.

**10.8 Revisão do João (portão):** mostre o PDF e peça que ele revise e reescreva Introdução, Metodologia e Considerações finais e confira as datas e situações do quadro. **Só depois disso:**
- `docs(p2): relatório consolidado P2 em Typst e PDF`, incluindo o `.typ` e o PDF.
- `docs: link do relatório P2 no README`.
- Push autorizado, **até 13/11/2026 23:59**. O primeiro commit do PDF tem de ser a versão real; **nunca um PDF provisório só para marcar data**.

---

## 11. Fase 6: Issues de entrega

- Prepare os corpos em `docs/entrega-ativ10.md`, `docs/entrega-ativ11.md` e `docs/entrega-p2.md`, no mesmo padrão de `docs/entrega-ativ9.md`.
- Abra cada issue com `gh issue create --title "<título exato>" --body-file <arquivo>` **só depois da confirmação do João**.
- **Imagens no corpo:** o `gh` não anexa imagem. Referencie os prints já commitados com link fixo no commit: `![landing](https://github.com/JoaoVSerrano/OficinaOS/blob/<sha>/docs/p2/prints/a10-01-landing.png?raw=true)`.

| Issue | Título exato | Corpo |
|---|---|---|
| A10 | `Entrega — Seu negócio no ar` | `@siriani`; link do commit; URL no ar; link do README (diagrama) e de `db/`; os 7 prints exigidos; nota honesta do atraso (planejada 06/11) |
| A11 | `Entrega — SaaS completo` | `@siriani`; link do commit; `.env.example`; os 5 prints exigidos; resumo de como testar (conta Free → limite → 4242 → portal) |
| P2 | `Entrega — P2` | `@siriani`; link do PDF em `docs/`; link do commit do PDF |

**Ordem (a P2 precisa das datas e prints das issues A10 e A11):**
1. Deploy da A10 → prints A10 → issue A10.
2. Deploy da A11 → prints A11 → issue A11 (até 13/11).
3. Prints das issues A10 e A11 → finalizar a P2 → commit do PDF → issue P2 (até 13/11 23:59).

---

## 12. Checklist final (marque aqui e commite com `docs:`)

**Atividade 10**
- [ ] A stack aponta para o OficinaOS e os containers estão saudáveis (print).
- [x] 3 ou mais tabelas do domínio com FK + `db/001_dominio.sql` + `db/002_seed.sql` versionados.
- [x] CRUD de OS na API e nas telas; Swagger atualizado e paridade verde.
- [ ] Papéis `admin`/`dono`/`mecanico`/`cliente`; ação proibida → 403 direto na API (teste + print).
- [ ] Outra oficina → 404 (teste + print).
- [ ] Eventos de negócio no log com quem e quando (print).
- [ ] Foto da OS no MinIO, ligada à OS e sem leitura pública (print).
- [ ] Landing pública com "Criar conta grátis" (print).
- [x] `git grep` do legado vazio; TMDB fora do código, do compose, do `.env.example` e da stack. (código, compose e `.env.example` prontos; falta remover da stack no Portainer)
- [ ] README com a URL no ar e o diagrama atualizado; menção a github.com/siriani.
- [ ] Issue `Entrega — Seu negócio no ar` aberta, com data e hora registradas.

**Atividade 11**
- [ ] Produtos Free (R$ 0) e Pro (R$ 49/mês) na Stripe em modo de teste.
- [ ] Checkout de assinatura por oficina (só dono).
- [ ] 4 webhooks: assinatura validada, idempotentes e com teste de evento repetido e fora de ordem.
- [ ] Portal com cancelamento imediato → volta ao Free pelo webhook.
- [ ] Limites do Free → 402 com mensagem (21ª OS, 2º mecânico, 4º anexo).
- [ ] Painel admin: planos, assinaturas ativas, MRR de teste e eventos (só admin).
- [ ] `.env.example` só com nomes; nenhum segredo no git (`git grep -nE "sk_(test|live)_[A-Za-z0-9]{10,}|whsec_[A-Za-z0-9]{10,}"` vazio, fora os valores fictícios dos testes).
- [ ] Issue `Entrega — SaaS completo` aberta até 13/11.

**P2**
- [ ] `docs/P2_ISW055_Joao_Serrano.pdf` gerado do template, sem marcas do template, com todas as figuras.
- [ ] Arquitetura igual à stack no ar; quadro de 7 a 11 com datas e situações reais.
- [ ] Introdução e Metodologia revisadas pelo João, com pelo menos 2 parágrafos cada.
- [ ] Link do PDF no README; primeiro commit do PDF até 13/11/2026 23:59; issue `Entrega — P2` aberta.

**Sempre**
- [ ] `pytest` verde localmente (152 testes) e no CI; commits pequenos em Conventional Commits. (local: ok; falta o CI após o push)

---

## 13. Cronograma sugerido e corte de escopo

| Dia | Foco |
|---|---|
| **Qua 11/11** | Fase 0; T10.1–T10.12 (banco, papéis, API, isolamento, log, anexos, limpeza do backend) com testes |
| **Qui 12/11** | T10.13–T10.17 (frontend, landing, compose, docs, cenário) → deploy A10 → prints A10 → issue A10; T11.1–T11.6 |
| **Sex 13/11** | T11.7–T11.10 → configuração da Stripe → deploy A11 → prints A11 → issue A11 → relatório P2 → revisão do João → commit do PDF → issue P2 **até 23:59** |

**Se o tempo apertar, corte nesta ordem** e declare o que faltou nas fichas e nas issues, nunca escondendo:
1. Histórico do veículo de 30 dias.
2. Limite de anexos.
3. Tela de clientes e veículos detalhada (mantenha o mínimo para abrir uma OS).
4. Polimento visual.

**Nunca corte:**
- O 403 e o 404 no backend.
- Os webhooks idempotentes.
- Os limites de OS por mês e de mecânicos.
- O painel admin com MRR.
- A remoção do TMDB.
- O commit do PDF até 13/11.

---

## 14. O que depende do João

- Responder às perguntas da Fase 0.
- Autorizar cada push e cada abertura de issue.
- Criar os secrets do Actions no OficinaOS.
- No Portainer: trocar o repositório, ajustar as variáveis, cuidar da rede antiga, autorizar a migração destrutiva e fazer o redeploy.
- Na Stripe (modo de teste): produtos, portal com cancelamento imediato e endpoint de webhook com os 4 eventos.
- Fazer login nas janelas abertas para os prints do painel da Stripe, do Portainer e do MinIO, ou tirá-los manualmente com os nomes da tabela 9.3.
- Revisar e reescrever Introdução, Metodologia e Considerações finais e conferir o quadro de entregas antes do commit do PDF.
