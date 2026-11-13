// ============================================================
//  P2 — Relatório consolidado: arquitetura e atividades (INDIVIDUAL)
//  ISW055 · Introdução à Computação em Nuvem · Fatec Pompeia · 2026.2
//
//  COMO USAR
//  1. Preencha a seção DADOS DO ALUNO logo abaixo.
//  2. Escreva a seção "Arquitetura do SaaS" seguindo os subtítulos-guia.
//  3. Em cada #atividade(...), preencha "realizada", "situacao" e "url"
//     e escreva o corpo: o que você fez, prints e dificuldades.
//  4. Salve os prints numa pasta "prints/" ao lado deste arquivo e troque
//     `arquivo: none` por `arquivo: "prints/nome-do-print.png"`.
//  5. Compile em https://typst.app (Novo projeto → envie este arquivo e a
//     pasta prints) ou no terminal: typst compile P2_ISW055_template.typ
//  6. Apague os blocos cinza de orientação quando terminar.
//
//  Entrega: 13/11/2026 · PDF nomeado P2_ISW055_Nome_Sobrenome.pdf,
//  em docs/ do repositório do produto, com link no README e uma issue
//  "Entrega — P2" mencionando @siriani
// ============================================================

// ---------- DADOS DO ALUNO (edite aqui) ----------
#let aluno = "João Victor Serrano"
#let turma = "161_SIST. INTELIGENTES_N"
#let produto = "OficinaOS"
#let repositorio = "https://github.com/JoaoVSerrano/OficinaOS"
#let data-relatorio = "13/11/2026"

// ---------- daqui pra baixo, só mexa nas seções e nas fichas ----------
#let disciplina = "Introdução à Computação em Nuvem"
#let codigo = "ISW055"
#let professor = "Prof. Allan Lincoln Rodrigues Siriani"
#let accent = rgb("#b96f1f")

#set document(title: "P2 — " + codigo + " — " + aluno, author: aluno)
#set page(paper: "a4", margin: (top: 2.5cm, bottom: 2.5cm, left: 2.5cm, right: 2cm))
#set text(size: 11pt, lang: "pt", region: "BR")
#set par(justify: true, leading: 0.7em)
#set heading(numbering: "1.1")
#show heading.where(level: 1): it => { v(0.6em); text(size: 16pt, it); v(0.2em) }
#show heading.where(level: 2): it => { v(0.5em); text(size: 13pt, it); v(0.1em) }
#show link: set text(fill: accent)
#show figure.caption: set text(size: 9pt, fill: luma(90))
#set table(stroke: 0.5pt + luma(200), inset: 6pt)
#show table: set text(hyphenate: false)
#show table: set par(justify: false)

// ---------- ajudantes ----------
#let orientacao(body) = block(
  width: 100%, fill: luma(245), inset: 9pt, radius: 4pt,
  stroke: (left: 2pt + luma(180)),
  text(size: 9.5pt, fill: luma(90), body),
)

#let evidencia(legenda, arquivo: none) = figure(
  if arquivo == none {
    rect(width: 100%, height: 5.5cm, radius: 4pt, stroke: (paint: luma(170), dash: "dashed"))[
      #align(center + horizon)[
        #text(fill: luma(130), size: 9.5pt)[
          cole o print ou o diagrama aqui \
          troque `arquivo: none` por `arquivo: "prints/nome.png"`
        ]
      ]
    ]
  } else {
    image(arquivo, width: 100%)
  },
  kind: image,
  supplement: [Figura],
  caption: legenda,
)

// Marcadores de revisão (apagar antes da entrega): rascunho = texto que o João reescreve com as próprias palavras;
// pendente = dado que só existe depois do deploy, das issues ou que só o João sabe.
#let rascunho(body) = block(width: 100%, inset: (left: 8pt, y: 4pt), stroke: (left: 2pt + rgb("#c2410c")))[
  #text(size: 8pt, weight: "bold", fill: rgb("#c2410c"))[RASCUNHO — reescreva com as suas palavras] \
  #body
]
#let pendente(body) = highlight(fill: rgb("#fde68a"))[#text(fill: rgb("#7c2d12"))[[PENDENTE: #body]]]

#let registro = state("registro", ())

#let registrar(numero, titulo, planejada, realizada, situacao) = registro.update(l => l + ((
  numero: numero, titulo: titulo,
  planejada: planejada, realizada: realizada, situacao: situacao,
),))

#let atividade(
  numero, titulo,
  descricao: "",
  planejada: "",
  realizada: "—",
  situacao: "entregue",   // entregue · entregue com atraso · não entregue
  evidencia: "",
  url: "",
  corpo,
) = {
  registrar(numero, titulo, planejada, realizada, situacao)
  heading(level: 2, [Atividade #numero — #titulo])
  table(
    columns: (3.4cm, 1fr),
    fill: (x, y) => if x == 0 { luma(245) } else { none },
    [*Descrição*], [#descricao],
    [*Data planejada*], [#planejada],
    [*Data realizada*], [#realizada],
    [*Situação*], [#situacao],
    [*Evidência*], [#evidencia],
    [*Link*], [#if url == "" [—] else [#link(url)]],
  )
  corpo
}

// ============================================================
//  CAPA
// ============================================================
#align(center)[
  #v(2.5cm)
  #text(size: 12pt, tracking: 0.12em)[FATEC POMPEIA]
  #v(0.4em)
  #text(size: 10.5pt, fill: luma(110))[#disciplina · #codigo · #turma]
  #v(4cm)
  #text(size: 26pt, weight: "bold")[P2]
  #v(0.3em)
  #text(size: 18pt, weight: "bold")[Relatório consolidado]
  #v(0.2em)
  #text(size: 13pt)[arquitetura e atividades do 2º bimestre]
  #v(0.8em)
  #text(size: 11pt, fill: luma(110))[Avaliação individual · 2026.2]
  #v(3.2cm)
  #text(size: 14pt)[#aluno]
  #v(0.5em)
  #text(size: 11pt)[Produto: *#produto*] \
  #text(size: 9.5pt)[#link(repositorio)]
  #v(1fr)
  #text(size: 10.5pt)[#professor \ Pompeia, #data-relatorio]
]

#set page(
  numbering: "1",
  number-align: right,
  header: context {
    set text(size: 8pt, fill: luma(120))
    [#codigo · P2 — Relatório consolidado #h(1fr) #aluno]
    line(length: 100%, stroke: 0.4pt + luma(200))
  },
)
#counter(page).update(1)

#outline(title: "Sumário", indent: 1.2em, depth: 2)
#pagebreak()

// ============================================================
= Introdução
// ============================================================
#rascunho[
Este relatório consolida o 2º bimestre da disciplina Introdução à Computação em Nuvem (ISW055), da Fatec Pompeia. A disciplina parte de um sistema real implantado em nuvem e o faz evoluir até um SaaS completo: com microsserviços em containers, autenticação com papéis, auditoria, armazenamento de objetos, cobrança recorrente e observabilidade, tudo rodando numa stack do Portainer, na VM da Fatec.

No 1º bimestre o projeto era um catálogo de filmes do Tom Hanks. Na atividade 9 ele foi copiado com todo o histórico para um repositório novo e virou o *OficinaOS*: um sistema de ordens de serviço para oficinas mecânicas pequenas, que hoje controlam o serviço no caderno, em planilha e no WhatsApp. O dono da oficina abre a ordem de serviço, monta e envia o orçamento, o cliente aprova pelo celular, o mecânico acompanha o que foi atribuído a ele e o dono registra o pagamento na entrega. O produto é vendido em dois planos (Free e Pro), cobrados pela Stripe em modo de teste.

O relatório descreve primeiro a arquitetura do sistema que está no ar (componentes, onde roda, fluxos, modelo de dados, segurança, observabilidade e camadas de nuvem), depois traz o quadro de entregas e uma ficha por atividade, da 7 à 11, com as evidências e as dificuldades, e termina com as considerações finais.
]

// ============================================================
= Metodologia
// ============================================================
#rascunho[
As atividades 7 e 8 foram feitas no repositório público do catálogo de filmes (`JoaoVSerrano/tomhanks`), o mesmo do 1º bimestre. Na atividade 9, esse repositório foi copiado com todo o histórico (`git clone --bare` + `git push --mirror`) para o `JoaoVSerrano/OficinaOS`, onde o SaaS foi desenvolvido nas atividades 10 e 11, na mesma stack do Portainer e no mesmo domínio. O código é Python (Flask) no backend e nos microsserviços, Angular no frontend, MariaDB como banco e Docker Compose para subir tudo; a cada push na `main`, o GitHub Actions roda os testes, publica as imagens no GHCR e aciona o redeploy da stack.

O desenvolvimento seguiu testes antes do código (pytest, com SQLite em memória para o gateway e os serviços), commits pequenos no padrão Conventional Commits e, para cada atividade, um cenário de aceite em `scripts/cenarios/` que executa o roteiro do professor contra o sistema rodando e imprime PASS/FAIL por passo. Antes do deploy, tudo foi validado numa stack local com um MariaDB próprio, sem tocar no banco da turma. Usei o Claude Code como ferramenta de apoio na escrita do código, dos testes e na montagem deste relatório; revisei e decidi cada mudança.

A data e a hora de cada entrega foram extraídas do histórico de commits (`git log`) e, da atividade 9 em diante, da issue de entrega que menciona o professor. Os prints do sistema foram capturados com um navegador real (Chromium via Playwright, janela de 1440×900, fuso America/Sao\_Paulo), sem nenhuma edição; nas páginas do GitHub, que mostram datas relativas, o componente de data da própria página foi configurado para exibir o valor absoluto que ele já contém. Os prints que dependem de login em serviços de terceiros (painel da Stripe e Portainer) foram tirados por mim.
]

// ============================================================
= Arquitetura do SaaS
// ============================================================

== Visão geral e componentes

O OficinaOS é um conjunto de microsserviços na mesma rede Docker. Só o `app` é publicado pelo domínio; os outros serviços existem apenas na rede interna `oficinaos-net` e se autenticam entre si com o cabeçalho `X-Internal-Token`. A Stripe é externa e fala com o sistema de duas formas: o `payment-service` chama a API dela, e ela devolve os eventos pelo webhook público, que o `app` repassa sem alterar.

#evidencia([Diagrama de componentes e microsserviços do OficinaOS], arquivo: "prints/diagrama-arquitetura.png")

#table(
  columns: (3cm, 1fr, 3.2cm, 2.4cm),
  fill: (x, y) => if y == 0 { luma(235) } else { none },
  table.header([*Componente*], [*Responsabilidade*], [*Tecnologia / imagem*], [*Público?*]),
  [app], [gateway da API do negócio (oficinas, clientes, veículos, OS, orçamentos, catálogo, financeiro, anexos), landing page e telas Angular, proxy para os serviços internos], [Flask + Angular 21; `ghcr.io/joaovserrano/oficinaos-app`], [sim (domínio, porta 8080)],
  [auth-service], [login, cadastro, sessão, papéis (admin, dono, mecânico, cliente), vínculo com a oficina, perfil e avatar], [Flask + Gunicorn; `oficinaos-auth-service`], [não (3000, interno)],
  [log-service], [eventos de negócio e auditoria: quem, papel, oficina, recurso e quando], [Flask + Gunicorn; `oficinaos-log-service`], [não (4000, interno)],
  [payment-service], [checkout e portal da Stripe, webhooks idempotentes, tabela `assinaturas`, plano da oficina e números do painel (MRR)], [Flask + Gunicorn; `oficinaos-payment-service`], [não (5000, interno)],
  [Redis], [Redis Streams com os eventos do log; rate limit], [`redis:7-alpine`], [não],
  [MariaDB], [dados do domínio, usuários, assinaturas (externo: banco da turma)], [MariaDB do professor], [não],
  [MinIO], [fotos da OS em bucket privado (lidas só pela rota do gateway) e avatares], [`cgr.dev/chainguard/minio`], [não],
  [Prometheus e Grafana], [coleta de `/metrics` e dashboards], [imagens oficiais (portas 9091 e 3002)], [não pelo domínio],
  [Stripe (externo)], [checkout de assinatura, portal do cliente, webhooks], [serviço SaaS, modo de teste], [webhook → app],
)

== Onde roda

O sistema roda na mesma stack do Portainer usada desde o começo do semestre, na VM da Fatec (Proxmox com Ubuntu e Docker), publicado pelo mesmo domínio. A stack puxa o `docker-compose.yml` do repositório `JoaoVSerrano/OficinaOS` (branch `main`) e as imagens `oficinaos-*` publicadas no GitHub Container Registry pelo CI. São oito containers (app, auth-service, log-service, payment-service, redis, minio, prometheus e grafana), cada um com `mem_limit: 1g`, na rede `oficinaos-net` (subnet fixa 10.201.0.0/24). O MariaDB é o banco da turma, externo à stack; as migrações Alembic de cada serviço rodam sozinhas quando os containers sobem.

As variáveis de ambiente ficam só na seção *Environment* da stack; o repositório tem apenas o `.env.example`, com os nomes e valores fictícios: `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `FLASK_SECRET_KEY`, `AUTH_SECRET_KEY`, `AUTH_ADMIN_EMAIL`, `AUTH_ADMIN_PASSWORD`, `INTERNAL_TOKEN`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET_NAME`, `MINIO_ANEXOS_BUCKET`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_ID`, `STRIPE_SUCCESS_URL`, `STRIPE_CANCEL_URL`, `PRO_VALOR_CENTAVOS`, `FRONTEND_URL`, `SMTP_*` e `GRAFANA_ADMIN_PASSWORD`.

== Fluxo de uma requisição

Exemplo: o mecânico marca a ordem de serviço como pronta. O papel e a oficina nunca vêm da requisição: o `app` pergunta ao `auth-service` quem é o usuário, e toda consulta ao banco é filtrada pela oficina dele.

#evidencia([Fluxo de uma requisição: mecânico marca a OS como pronta], arquivo: "prints/diagrama-fluxo-requisicao.png")

+ O navegador envia `POST /api/os/12/status` com o cookie de sessão.
+ O `app` consulta `GET /me` no `auth-service` e recebe o id, o papel (`mecanico`) e a `oficina_id`.
+ O `app` busca a OS 12 *filtrando pela oficina do usuário e, para o mecânico, pelas OS atribuídas a ele*. Se não achar, responde 404 sem dizer se a OS existe em outra oficina.
+ A máquina de estados confere a transição (`em_servico → pronta` é permitida ao mecânico; transição inexistente dá 409, papel sem permissão dá 403 e gera o evento `acesso_negado`).
+ O `app` grava o novo status e envia ao `log-service` o evento `os.status_alterado` com usuário, papel, oficina e recurso; a resposta é 200 com a OS atualizada.

== Fluxo de assinatura

#evidencia([Fluxo de assinatura: checkout → webhook → plano no banco → limite liberado, e o cancelamento pelo portal], arquivo: "prints/diagrama-fluxo-assinatura.png")

Quem assina é a *oficina* (o tenant), não o usuário: só o dono inicia o checkout, e o `customer` da Stripe fica na tabela `assinaturas`, uma linha por oficina, ligada ao `usuario_id` do dono que assinou. O checkout é uma sessão `mode=subscription` com `client_reference_id` e metadata da oficina; o cartão nunca passa pelo servidor. Ao voltar, a tela mostra "processando…": o plano *só muda quando o webhook chega*, nunca pelo retorno do navegador.

O webhook é validado com `stripe.Webhook.construct_event` e o segredo `whsec_` (assinatura inválida → 400). Os quatro eventos são tratados: `checkout.session.completed` grava customer e subscription e muda para Pro; `customer.subscription.updated` atualiza status, valor e renovação; `customer.subscription.deleted` volta ao Free; `invoice.payment_failed` marca inadimplência, que aparece como aviso na tela. O efeito e o registro do evento em `processed_webhook_events` acontecem na *mesma transação*: evento repetido é ignorado, evento mais antigo que o último aplicado (`ultimo_evento_em`) não desfaz o mais novo e, se o efeito falhar, a resposta é 500 e a Stripe reenvia. Os limites do Free (20 OS por mês, 1 mecânico, 3 anexos por OS) são checados no gateway a cada requisição, lendo o plano do banco pelo `payment-service` (sem consultar a Stripe e sem cache); ao passar do limite a API responde 402 com a explicação e o caminho para assinar. O cancelamento é feito no portal do cliente da Stripe (configurado para cancelamento imediato) e chega pelo `customer.subscription.deleted`.

== Modelo de dados do domínio

Toda tabela do negócio tem `oficina_id`, direto ou pela OS (`os_id`). Dinheiro é sempre inteiro em centavos. `usuarios` fica no `auth-service` e `assinaturas` no `payment-service`: as referências entre serviços (`usuario_id`, `mecanico_id`, `oficina_id` em `usuarios` e em `assinaturas`) não têm chave estrangeira, porque cada serviço tem as próprias migrações e pode ser implantado sozinho; a consistência é garantida pelo gateway, que só usa ids vindos da sessão.

#evidencia([Modelo de dados do domínio (gateway), com usuários e assinaturas dos outros serviços], arquivo: "prints/diagrama-modelo-dados.png")

== Segurança

#table(
  columns: (1fr, 1.6cm, 2.4cm, 2.4cm, 2.6cm),
  align: (left, center, center, center, center),
  fill: (x, y) => if y == 0 { luma(235) } else { none },
  table.header([*Ação*], [*admin*], [*dono*], [*mecânico*], [*cliente*]),
  [criar a oficina, ver equipe e código de convite], [não], [sim], [não], [não],
  [cadastrar clientes, veículos e catálogo], [não], [sim], [não (lê o catálogo)], [não],
  [abrir e editar OS, itens e fotos], [não], [sim], [só as atribuídas], [não],
  [ver ordens de serviço], [não], [todas da oficina], [só as atribuídas], [só dos próprios veículos],
  [enviar orçamento], [não], [sim], [não], [não],
  [aprovar ou recusar orçamento], [não], [sim], [não], [o próprio (app ou link)],
  [anotações internas da OS], [não], [sim], [só as atribuídas], [não],
  [registrar pagamento e ver o financeiro], [não], [sim], [não], [não],
  [assinar o Pro e abrir o portal], [não], [sim], [não], [não],
  [ver os dados de outra oficina], [não], [não (404)], [não (404)], [não (404)],
  [painel da plataforma (planos, MRR, eventos)], [sim], [não], [não], [não],
)

*Isolamento.* O `oficina_id` vem sempre do usuário autenticado, nunca de parâmetro, corpo ou URL, e toda consulta do domínio passa por `backend/escopo.py`, que acrescenta o filtro da oficina (e, para as tabelas filhas, chega à oficina pela OS). Registro de outra oficina responde 404, sem revelar que existe; papel sem permissão, 403; sem login, 401. As permissões são checadas no backend, mesmo que a tela esconda o botão, e cada tentativa negada vira o evento `acesso_negado` no log. O link público do orçamento usa um token aleatório de 256 bits do qual o banco guarda só o hash; a resposta pública não traz ids, e-mail nem telefone, não vai para cache e tem limite de tentativas por IP e por link.

*Segredos.* Chaves, senhas e tokens ficam só nas variáveis de ambiente da stack; o `.env` local está no `.gitignore` e o `.env.example` tem apenas nomes e valores fictícios (um teste falha se aparecer uma chave da Stripe com cara de real). A Stripe é usada só em modo de teste, os dados de cartão nunca passam pelo servidor e a assinatura do webhook é sempre validada.

== Observabilidade, CI/CD e documentação da API

Cada serviço expõe `/health` com verificação real das dependências (banco, Redis, MinIO e os outros serviços) e `/metrics` no formato do Prometheus, que alimenta um dashboard no Grafana. O pipeline do GitHub Actions roda os testes (`pytest`, mais de 350 casos), publica as quatro imagens no GHCR e aciona o webhook do Portainer, com um teste de fumaça no `/health` depois do deploy. A API está documentada em Swagger (`/docs`, que agrega gateway, auth e log); um teste de paridade falha se existir rota sem documentação ou documentação sem rota (71 operações no gateway).

== Camadas IaaS, PaaS e SaaS do projeto

#table(
  columns: (2cm, 1fr, 3.6cm),
  fill: (x, y) => if y == 0 { luma(235) } else { none },
  table.header([*Camada*], [*O que é no seu projeto*], [*Quem gerencia*]),
  [IaaS], [a VM no Proxmox da Fatec (Ubuntu), a rede, o disco e o acesso pelo domínio], [professor / Fatec],
  [PaaS], [Docker + Portainer (a stack, os containers e o redeploy pelo webhook), o MariaDB da turma e os serviços de apoio da stack (Redis, MinIO, Prometheus, Grafana)], [dividido: o professor mantém o Portainer e o MariaDB; eu configuro a stack, as variáveis e os containers dela],
  [SaaS], [o OficinaOS, usado pelas oficinas pelo navegador sem instalar nada; e os SaaS que o projeto consome: Stripe (cobrança), GitHub (código, Actions, GHCR) e Google (login)], [eu (o OficinaOS); os fornecedores (Stripe, GitHub, Google)],
)

// ============================================================
= Quadro de entregas
// ============================================================

#context {
  let l = registro.final().sorted(key: a => a.numero)
  table(
    columns: (auto, 1fr, 2.3cm, 3.6cm, 2.4cm),
    align: (center, left, center, center, center),
    fill: (x, y) => if y == 0 { luma(235) } else { none },
    table.header([*Nº*], [*Atividade*], [*Data \ planejada*], [*Data \ realizada*], [*Situação*]),
    ..l.map(a => ([#a.numero], [#a.titulo], [#a.planejada], [#a.realizada], [#a.situacao])).flatten(),
  )
}

// ============================================================
= Atividades realizadas
// ============================================================

#atividade(
  7, "Plano Premium — cobrança de verdade com Stripe",
  descricao: "Plano pago em modo de teste: Checkout Session do Stripe e webhook marcando o usuário como premium.",
  planejada: "09/10/2026",
  realizada: "—",
  situacao: "não entregue",
  evidencia: "—",
  url: "",
)[
  *O que foi feito e o que faltou.* No repositório do catálogo de filmes há commits de 09/10/2026 (22:34–22:45) que criam o `payment-service` com Checkout Session, portal e webhook em modo de teste, mas declaro a atividade 7 como *não entregue*: #pendente[explique aqui o que faltou e por quê, com as suas palavras].

  Parte do que foi iniciado nesta atividade foi reaproveitado e refeito na atividade 11, em que a assinatura passou a ser da oficina, gravada no banco pelos webhooks.
]

#atividade(
  8, "SaaS, PaaS, IaaS — e a documentação que o projeto nunca teve",
  descricao: "Camadas de nuvem do próprio projeto e documentação reversa: especificação, arquitetura, regras de negócio e modelo de dados.",
  planejada: "16/10/2026",
  realizada: "23/10/2026 19:13",
  situacao: "entregue com atraso",
  evidencia: "GitHub — commit 2061f81 + DOCUMENTACAO.md linkado no README",
  url: "https://github.com/JoaoVSerrano/tomhanks/commit/2061f81",
)[
  *O que foi feito.* Classifiquei as camadas do projeto (a VM e a rede como IaaS; Docker, Portainer, MariaDB, Redis e MinIO como PaaS; o sistema como SaaS) e escrevi a documentação reversa do catálogo de filmes em `DOCUMENTACAO.md`: especificação, arquitetura, regras de negócio e modelo de dados, com o link no README.

  ```
  $ git log -1 --date=format:"%d/%m/%Y %H:%M" --format="%h %ad %s" 2061f81
  2061f81 23/10/2026 19:13 docs: classificação SaaS/PaaS/IaaS e documentação reversa (ativ. 8)
  ```

  #evidencia([Atividade 8 — commit 2061f81 no repositório tomhanks, com hash, data e hora (DOCUMENTACAO.md criado e README alterado)], arquivo: "prints/a08-01-commit.png")

  *Dificuldades e como foram resolvidas.* #pendente[motivo do atraso de uma semana e como foi resolvido]
]

#atividade(
  9, "Fork e plano de negócio",
  descricao: "Repositório novo com o histórico do anterior, README do produto (dor, persona, Lean Canvas, modelo de receita, mapa de reaproveitamento) e backlog em issues.",
  planejada: "23/10/2026",
  realizada: "11/11/2026 20:35",
  situacao: "entregue com atraso",
  evidencia: "GitHub — issue de entrega #11 (@siriani) + repositório novo + README do produto (commit d8abb36, 23/10/2026 20:14) + backlog de 10 issues",
  url: "https://github.com/JoaoVSerrano/OficinaOS/issues/11",
)[
  *O que foi feito.* Copiei o repositório do catálogo de filmes com todo o histórico (`git clone --bare` + `git push --mirror`) para o `OficinaOS`, deixei no repositório antigo um aviso apontando para o novo e escrevi o README do produto: a dor das oficinas pequenas, a persona, os concorrentes, a proposta de valor, o modelo de receita (Free e Pro a R\$ 49/mês), as métricas, o Lean Canvas e o mapa do que cada peça do projeto antigo viraria. O backlog das atividades 10 e 11 virou 10 issues. O trabalho ficou pronto em 23/10/2026, mas a issue de entrega só foi aberta em 11/11/2026; por isso a declaro entregue com atraso (a data que vale é a da issue).

  ```
  $ git log -1 --date=format:"%d/%m/%Y %H:%M" --format="%h %ad %s" d8abb36
  d8abb36 23/10/2026 20:14 docs: README do produto OficinaOS com plano de negócio, Lean Canvas e mapa de reaproveitamento
  ```

  #evidencia([Atividade 9 — issue de entrega \#11, aberta em 11/11/2026 20:35], arquivo: "prints/a09-01-issue.png")
  #evidencia([Atividade 9 — aba Commits do OficinaOS em 23/10/2026, com o README do produto], arquivo: "prints/a09-02-commits.png")
  #evidencia([Atividade 9 — backlog de issues do OficinaOS], arquivo: "prints/a09-03-issues.png")

  *Dificuldades e como foram resolvidas.* #pendente[por que a issue de entrega foi aberta só em 11/11]
]

#atividade(
  10, "Seu negócio no ar — o domínio no lugar dos filmes",
  descricao: "Stack apontando para o repositório novo, tabelas e API do domínio, papéis do negócio, isolamento por usuário, eventos no log, upload e landing page.",
  planejada: "06/11/2026",
  realizada: "PENDENTE",
  situacao: "entregue com atraso",
  evidencia: "GitHub — issue de entrega (@siriani) + commit + URL no ar + prints da landing, do 403 e dos eventos no log",
  url: "",
)[
  *O que foi feito.* Troquei o domínio de filmes pelo de oficina mecânica: tabelas `oficinas`, `clientes`, `veiculos`, `ordens_servico`, `itens_os` e `anexos_os` com chaves estrangeiras e migração Alembic (`3450d65`), SQL e seed versionados (`e963f21`), papéis `dono`, `mecanico` e `cliente` com vínculo à oficina (`d451bdc`), escopo obrigatório por oficina em toda consulta (`02cdb2a`), cadastro por código de convite (`2531ede`), ordens de serviço com itens e máquina de estados (`65a4437`), eventos de negócio no log (`875ec87`), fotos da OS no MinIO em bucket privado (`16aebc2`), remoção do catálogo de filmes e da TMDB (`f1e4158`) e um frontend novo, com landing pública e as telas do dia a dia da oficina (`2ee9b5a`). O roteiro do professor virou o cenário `scripts/cenarios/ativ10.py`, que passa nos 35 passos na stack local. Data realizada: #pendente[data e hora da issue de entrega da A10].

  #evidencia([Atividade 10 — issue de entrega com data e hora visíveis])
  #evidencia([Atividade 10 — landing page no ar])
  #evidencia([Atividade 10 — 403 ao usar uma ação proibida ao papel, chamando a API direto])
  #evidencia([Atividade 10 — 404 ao abrir a OS de outra oficina])
  #evidencia([Atividade 10 — eventos de negócio no log, com quem e quando])
  #evidencia([Atividade 10 — foto da OS no MinIO])
  #evidencia([Atividade 10 — stack no Portainer com os containers saudáveis])

  *Dificuldades e como foram resolvidas.* #pendente[motivo do atraso]. A migração que apaga as tabelas antigas (`favoritos` e `comentarios`) roda no banco da turma no deploy, então todo o desenvolvimento foi validado antes numa stack local com MariaDB próprio, e o push só foi feito depois de conferir o roteiro inteiro.
]

#atividade(
  11, "SaaS completo — planos, limites e assinatura com Stripe",
  descricao: "Planos recorrentes, checkout de assinatura, webhooks atualizando o plano, portal do cliente, limites por plano na API e painel admin.",
  planejada: "13/11/2026",
  realizada: "PENDENTE",
  situacao: "entregue",
  evidencia: "GitHub — issue de entrega (@siriani) + commit + prints da assinatura com o cartão 4242, do Stripe em modo de teste, do webhook e do limite bloqueando",
  url: "",
)[
  *O que foi feito.* A assinatura passou a ser da oficina, numa tabela `assinaturas` atualizada só pelos webhooks (`749fe6b`). Os quatro webhooks são idempotentes e aplicados na mesma transação do registro do evento (`dde8494`); o valor mensal vem do evento da Stripe (`dc87316`). O checkout (`9517f7f`) e o portal (`43ba84a`) são só do dono, os limites do Free são aplicados na API com o plano lido do banco a cada requisição (`9663108`, `ef228af`) e o painel do admin mostra oficinas e usuários por plano, assinaturas ativas, MRR de teste e os últimos eventos (`e227d54`). A tela "Plano e assinatura" mostra o uso, assina, abre o portal e avisa de limite e de inadimplência (`f726d73`). Além do pedido, o produto ganhou orçamento com versões e link para o cliente aprovar sem login, catálogo de serviços e peças, histórico do veículo, pagamentos na entrega e o financeiro do mês (`56823f0` a `2f6760d`). Os cenários `ativ11.py` (36 passos) e `ativ12.py` (41 passos) passam na stack local. Data realizada: #pendente[data e hora da issue de entrega da A11].

  #evidencia([Atividade 11 — issue de entrega com data e hora visíveis])
  #evidencia([Atividade 11 — 21ª OS recusada no Free com a mensagem do plano])
  #evidencia([Atividade 11 — checkout da Stripe em modo de teste com o cartão 4242])
  #evidencia([Atividade 11 — assinaturas no painel da Stripe com o selo de modo de teste])
  #evidencia([Atividade 11 — webhook entregue com 200 e o evento assinatura.ativada no log])
  #evidencia([Atividade 11 — painel admin com planos, assinaturas ativas e MRR de teste])

  *Dificuldades e como foram resolvidas.* A versão herdada da atividade 7 consultava a Stripe ao vivo, por `google_id`, com cache no Redis, e marcava o evento como processado antes de aplicar o efeito: se algo falhasse, a Stripe não reenviava. Refiz o fluxo para o plano ser uma cópia no banco atualizada só pelos webhooks, com idempotência na mesma transação e proteção contra eventos fora de ordem, e removi a consulta ao vivo. Os testes com eventos assinados por um segredo fictício permitiram validar os quatro eventos sem depender do cartão.
]


// ============================================================
= Considerações finais
// ============================================================
#rascunho[
O bimestre mostrou na prática a diferença entre um sistema que roda e um SaaS: isolar os dados de cada cliente em toda consulta, aceitar que a fonte da verdade da cobrança é a Stripe (e que o banco só guarda uma cópia mantida pelos webhooks), não confiar em nada que vem do navegador e conseguir provar o que está no ar com testes, logs e prints. A parte mais difícil foi a cobrança: tratar evento repetido, fora de ordem e falha no meio do processamento muda o desenho inteiro do webhook.

Se recomeçasse, faria o modelo de dados do negócio antes de qualquer tela e entregaria cada atividade com a issue no mesmo dia, para não acumular atrasos. Para o OficinaOS virar um produto de verdade, faltam a emissão de nota fiscal, o envio do orçamento pelo WhatsApp de forma automática, o controle de estoque de peças e a cobrança em produção (fora do modo de teste), com termos de uso e LGPD.
]

// ============================================================
= Declaração de autoria
// ============================================================
Declaro que este relatório foi elaborado por mim, individualmente, e que as evidências apresentadas correspondem a entregas de minha autoria, verificáveis nos links informados.

#v(1.5cm)
#grid(
  columns: (1fr, 1fr), gutter: 2cm,
  align(center)[#line(length: 100%, stroke: 0.5pt) \ #aluno],
  align(center)[#line(length: 100%, stroke: 0.5pt) \ Pompeia, #data-relatorio],
)
