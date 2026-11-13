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
#let aluno = "Nome Completo do Aluno"
#let turma = "161_SIST. INTELIGENTES_N"
#let produto = "Nome do Produto"
#let repositorio = "https://github.com/SEU-USUARIO/NOME-DO-PRODUTO"
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
#orientacao[
  *O que escrever aqui (2–4 parágrafos):* qual é a disciplina e o que ela se propõe; como o projeto saiu de um catálogo de filmes e virou o seu SaaS; qual é a dor que o produto resolve e pra quem; o que este relatório contém e como está organizado. Escreva pra alguém que não assistiu às aulas. Apague este bloco ao terminar.
]

Escreva aqui a sua introdução.

// ============================================================
= Metodologia
// ============================================================
#orientacao[
  *O que escrever aqui:* como as atividades foram feitas (ferramentas, ambiente, fontes), como as evidências foram coletadas e de onde saíram as datas e horas de entrega. O parágrafo abaixo é um ponto de partida — ajuste para a sua realidade.
]

As atividades 7 e 8 foram feitas no repositório público do catálogo de filmes, o mesmo do 1º bimestre. Na atividade 9, esse repositório foi copiado com todo o histórico (`git clone --bare` + `git push --mirror`) para um repositório novo, com o nome do produto, onde o SaaS foi desenvolvido nas atividades 10 e 11, na mesma stack do Portainer e no mesmo domínio. A data e a hora de cada entrega foram extraídas do histórico de commits (`git log`), conferidas na página do commit no GitHub e, da atividade 9 em diante, na issue de entrega que menciona o professor. Os prints mostram o README com a menção ao professor, o histórico de commits e o sistema em execução.

// ============================================================
= Arquitetura do SaaS
// ============================================================
#orientacao[
  Descreva o sistema *que está no ar*, não um projeto ideal: o que estiver no diagrama tem que existir na stack. Diagramas podem ser feitos em qualquer ferramenta (draw.io, Excalidraw, Mermaid…) e entrar como imagem. Apague os blocos cinza e as linhas de exemplo das tabelas ao terminar.
]

== Visão geral e componentes
#orientacao[
  Um diagrama com todos os componentes e como eles conversam: o app do negócio, o auth-service (login + RBAC), o log-service com Redis, o MariaDB, o MinIO e o Stripe (checkout, webhooks, portal). Indique quem chama quem e o que é público (passa pelo domínio) e o que só existe na rede interna do Docker. Complete a tabela.
]

#evidencia([Diagrama de componentes e microsserviços do SaaS])

#table(
  columns: (3cm, 1fr, 3.2cm, 2.4cm),
  fill: (x, y) => if y == 0 { luma(235) } else { none },
  table.header([*Componente*], [*Responsabilidade*], [*Tecnologia / imagem*], [*Público?*]),
  [app], [telas, API do negócio, landing page], [...], [sim (domínio)],
  [auth-service], [login, cadastro, papéis (RBAC)], [...], [...],
  [log-service], [eventos de negócio e auditoria], [...], [...],
  [Redis], [armazenamento dos logs], [...], [...],
  [MariaDB], [dados do domínio, usuários, planos], [...], [...],
  [MinIO], [arquivos do domínio], [...], [...],
  [Stripe (externo)], [checkout, assinaturas, portal, webhooks], [serviço SaaS], [webhook → app],
)

== Onde roda
#orientacao[
  A mesma stack do Portainer, na mesma VM e no mesmo domínio usados desde o começo do semestre: o nome da stack, o repositório de onde ela puxa o código (o novo), os containers e os limites de memória, os nomes das variáveis de ambiente (*nunca os valores*) e a URL pública.
]

Escreva aqui onde e como o sistema roda.

== Fluxo de uma requisição
#orientacao[
  Escolha uma ação comum do seu negócio (ex.: "passageiro reserva uma vaga") e descreva o caminho completo: navegador → domínio → app → auth-service (sessão/token e papel) → MariaDB → log-service → resposta. Um diagrama de sequência ou uma lista numerada.
]

Descreva aqui o fluxo de uma requisição.

== Fluxo de assinatura
#orientacao[
  Do clique em "Assinar" até o limite liberado: checkout (`mode=subscription`) → pagamento no Stripe → webhook (`checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_failed`) → plano atualizado no banco → limites aplicados na API. Diga como o webhook é validado e o que acontece se o mesmo evento chegar duas vezes. Inclua o cancelamento pelo portal do cliente.
]

#evidencia([Fluxo de assinatura: checkout → webhook → plano no banco])

== Modelo de dados do domínio
#orientacao[
  Diagrama entidade-relacionamento (ou uma tabela por tabela) com as tabelas do negócio, as chaves estrangeiras e as colunas que ligam usuário, plano e assinatura do Stripe.
]

#evidencia([Modelo de dados do domínio])

== Segurança
#orientacao[
  Os papéis e o que cada um pode fazer (complete a tabela), como o isolamento por usuário é garantido nas consultas (cada usuário só vê os próprios dados), e onde ficam os segredos: variáveis de ambiente da stack, nunca o repositório, com um `.env.example` só com os nomes.
]

#table(
  columns: (1fr, 2.4cm, 2.4cm, 2.4cm),
  align: (left, center, center, center),
  fill: (x, y) => if y == 0 { luma(235) } else { none },
  table.header([*Ação*], [*admin*], [*papel 2*], [*papel 3*]),
  [criar ...], [sim], [sim], [não],
  [ver os dados de outro usuário], [sim], [não], [não],
  [...], [...], [...], [...],
)

Escreva aqui como o isolamento e os segredos são tratados.

== Observabilidade, CI/CD e documentação da API
#orientacao[
  Só se você fez as extras: health checks e métricas, o pipeline do GitHub Actions, o Swagger. Se não fez nenhuma, escreva uma linha dizendo isso e apague o resto.
]

Escreva aqui (ou declare que não se aplica).

== Camadas IaaS, PaaS e SaaS do projeto
#orientacao[
  Onde cada camada aparece no *seu* projeto e quem gerencia cada uma (você, o professor/Fatec, um fornecedor). É a atividade 8 aplicada ao produto final.
]

#table(
  columns: (2cm, 1fr, 3.6cm),
  fill: (x, y) => if y == 0 { luma(235) } else { none },
  table.header([*Camada*], [*O que é no seu projeto*], [*Quem gerencia*]),
  [IaaS], [a VM, a rede e o disco onde a stack roda: ...], [...],
  [PaaS], [Docker + Portainer, MariaDB, Redis, MinIO: ...], [...],
  [SaaS], [o seu produto, para o cliente final; e os SaaS que você usa (Stripe, GitHub): ...], [...],
)

// ============================================================
= Quadro de entregas
// ============================================================
#orientacao[
  Esta tabela é gerada automaticamente a partir das fichas da seção seguinte — não edite aqui; edite os campos `planejada`, `realizada` e `situacao` de cada `#atividade(...)`. *Atrasos:* cada atividade de 7 a 11 entregue com atraso ou não entregue desconta 0,25 da P2; a própria P2 perde 0,25 por dia depois de 13/11/2026, contado pelo primeiro commit do PDF.
]

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
#orientacao[
  Uma ficha completa por atividade, da 7 à 11, como na P1. Em cada uma: preencha *realizada* (dia e hora — DD/MM/AAAA HH:MM, do commit ou, da atividade 9 em diante, da issue de entrega), *situacao* (entregue · entregue com atraso · não entregue), *url* (link direto da evidência) e escreva abaixo da ficha o que foi feito, os prints e as dificuldades. *Atividade não entregue também entra* — com o que faltou e por quê: omitir conta contra, declarar não conta.
]

#atividade(
  7, "Plano Premium — cobrança de verdade com Stripe",
  descricao: "Plano pago em modo de teste: Checkout Session do Stripe e webhook marcando o usuário como premium.",
  planejada: "09/10/2026",
  realizada: "DD/MM/AAAA HH:MM",
  situacao: "entregue",
  evidencia: "GitHub — commit + print do checkout concluído e do usuário premium",
  url: "https://github.com/SEU-USUARIO/REPOSITORIO-ANTIGO",
)[
  *O que foi feito.* Descreva em um ou dois parágrafos o que você construiu nesta atividade e as decisões que tomou.

  #evidencia([Atividade 7 — evidência da entrega (link, data e hora visíveis)])
  #evidencia([Atividade 7 — resultado (o sistema funcionando)])

  *Dificuldades e como foram resolvidas.* Um parágrafo curto.
]

#atividade(
  8, "SaaS, PaaS, IaaS — e a documentação que o projeto nunca teve",
  descricao: "Camadas de nuvem do próprio projeto e documentação reversa: especificação, arquitetura, regras de negócio e modelo de dados.",
  planejada: "16/10/2026",
  realizada: "DD/MM/AAAA HH:MM",
  situacao: "entregue",
  evidencia: "GitHub — commit + DOCUMENTACAO.md linkado no README",
  url: "https://github.com/SEU-USUARIO/REPOSITORIO-ANTIGO",
)[
  *O que foi feito.* Descreva em um ou dois parágrafos o que você construiu nesta atividade e as decisões que tomou.

  #evidencia([Atividade 8 — evidência da entrega (link, data e hora visíveis)])
  #evidencia([Atividade 8 — resultado (o sistema funcionando)])

  *Dificuldades e como foram resolvidas.* Um parágrafo curto.
]

#atividade(
  9, "Fork e plano de negócio",
  descricao: "Repositório novo com o histórico do anterior, README do produto (dor, persona, Lean Canvas, modelo de receita, mapa de reaproveitamento) e backlog em issues.",
  planejada: "23/10/2026",
  realizada: "DD/MM/AAAA HH:MM",
  situacao: "entregue",
  evidencia: "GitHub — issue de entrega (@siriani) + repositório novo + README do produto + print do histórico de commits e das issues",
  url: "https://github.com/SEU-USUARIO/NOME-DO-PRODUTO",
)[
  *O que foi feito.* Descreva em um ou dois parágrafos o que você construiu nesta atividade e as decisões que tomou.

  #evidencia([Atividade 9 — evidência da entrega (link, data e hora visíveis)])
  #evidencia([Atividade 9 — resultado (o sistema funcionando)])

  *Dificuldades e como foram resolvidas.* Um parágrafo curto.
]

#atividade(
  10, "Seu negócio no ar — o domínio no lugar dos filmes",
  descricao: "Stack apontando para o repositório novo, tabelas e API do domínio, papéis do negócio, isolamento por usuário, eventos no log, upload e landing page.",
  planejada: "06/11/2026",
  realizada: "DD/MM/AAAA HH:MM",
  situacao: "entregue",
  evidencia: "GitHub — issue de entrega (@siriani) + commit + URL no ar + prints da landing, do 403 e dos eventos no log",
  url: "https://github.com/SEU-USUARIO/NOME-DO-PRODUTO",
)[
  *O que foi feito.* Descreva em um ou dois parágrafos o que você construiu nesta atividade e as decisões que tomou.

  #evidencia([Atividade 10 — evidência da entrega (link, data e hora visíveis)])
  #evidencia([Atividade 10 — resultado (o sistema funcionando)])

  *Dificuldades e como foram resolvidas.* Um parágrafo curto.
]

#atividade(
  11, "SaaS completo — planos, limites e assinatura com Stripe",
  descricao: "Planos recorrentes, checkout de assinatura, webhooks atualizando o plano, portal do cliente, limites por plano na API e painel admin.",
  planejada: "13/11/2026",
  realizada: "DD/MM/AAAA HH:MM",
  situacao: "entregue",
  evidencia: "GitHub — issue de entrega (@siriani) + commit + prints da assinatura com o cartão 4242, do Stripe em modo de teste, do webhook e do limite bloqueando",
  url: "https://github.com/SEU-USUARIO/NOME-DO-PRODUTO",
)[
  *O que foi feito.* Descreva em um ou dois parágrafos o que você construiu nesta atividade e as decisões que tomou.

  #evidencia([Atividade 11 — evidência da entrega (link, data e hora visíveis)])
  #evidencia([Atividade 11 — resultado (o sistema funcionando)])

  *Dificuldades e como foram resolvidas.* Um parágrafo curto.
]


// ============================================================
= Considerações finais
// ============================================================
#orientacao[
  *O que escrever aqui (1–3 parágrafos):* o que você aprendeu no bimestre, o que foi mais difícil, o que faria diferente no seu SaaS e o que ainda falta para ele ser um produto de verdade. Sem repetir a introdução.
]

Escreva aqui as suas considerações finais.

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
