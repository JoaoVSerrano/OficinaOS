# Decisões e desvios da execução (Atividades 10, 11 e P2)

Registro de tudo que divergiu do plano (`EXECUCAO.md`) ou que foi decidido durante a execução. O repositório vale mais que o plano.

## 11/11/2026: Fase 0

- **Linha de base de testes:** 43 testes passando (o plano dizia 37).
- **Arquivos soltos de uma tentativa anterior** (`backend/migrations/versions/0002_dominio.py`, `db/001_dominio.sql`, `db/002_seed.sql`) usavam outro modelo (`oficina_membros`, `cnpj`, FKs compostas). Decisão do João: seguir o plano. Os arquivos foram movidos para `.evidencias/tentativa-anterior/` (ignorado pelo git), sem apagar.
- **Issue `Entrega — Fork e plano de negócio` (A9) não existe.** O `gh issue list` só mostra as 10 issues do backlog, criadas em 23/10/2026 23:18 UTC. A situação da A9 depende do que o João decidir.
- **Escopo:** o João sobe a stack no Portainer; eu entrego o código local, os testes, o PDF e os checklists (`DEPLOY.md`). Stripe CLI autorizado (o `stripe login` é feito pelo João).
- **Ferramentas:** Typst 0.15.2 via `pip install typst` (sem binário CLI); Node local é 24, o plano citava 22.
- **CLAUDE.md:** a atualização prevista na seção 5.5 foi bloqueada pelo modo automático (edição de arquivo de instruções do próprio agente). Fica pendente de autorização do João.

## 11/11/2026: respostas do João
- `CLAUDE.md` atualizado com autorização explícita do João.
- **A9:** a issue de entrega não existia. João autorizou abri-la agora; o corpo declara a A9 como **entregue com atraso** (trabalho em 23/10/2026, issue em 11/11/2026). A data da issue é a que vale na ficha.
- **A8 e A10:** atrasos por motivos pessoais (sem justificativa técnica). A ficha dirá apenas isso.
- **A7:** sem print do resultado original; a ficha usa o commit no GitHub e diz isso na legenda.
- **A9, print original** do João (lista de issues): `docs/p2/prints/Captura de tela de 2026-11-11 20-32-08.png`, será renomeado para `a09-03-issues.png`. As datas aparecem relativas ("3w ago"); a data exata vem da issue/`gh`.
- Nome, turma e arquivo `P2_ISW055_Joao_Serrano.pdf` confirmados.

## 11/11/2026: Atividade 10 (implementação local)

- **Linha de base:** 43 testes; ao final da A10 local, 152 testes verdes. Cenário `scripts/cenarios/ativ10.py`: 35/35 passos contra a stack local (MariaDB 11, MinIO, Redis e log-service reais).
- **Revisão do gateway:** `0002_dominio_oficina` (como no plano). O baseline `0001_initial` virou neutro, sem apagar nem renomear.
- **Auth:** `/register` público ignora papel/oficina e cria `dono` sem oficina; o cadastro com papel e oficina só existe em `/internal/register` (token interno), chamado pelo gateway em `POST /api/cadastro`. Sem FK entre serviços (`usuarios.oficina_id`, `usuario_id`, `mecanico_id`).
- **Admin não opera oficina:** `admin` recebe 403 nas rotas do domínio (sem `oficina_id`); vê só auditoria global (`/api/admin/logs`) e, na A11, o painel. Diverge de "leitura para suporte" do plano; é mais simples e mais seguro.
- **Mecânico abre OS:** a OS fica atribuída a ele mesmo (ignora `mecanico_id` do corpo). Só o dono atribui mecânico, e o mecânico precisa ser da mesma oficina (confirmado no auth-service).
- **Itens da OS** só podem ser alterados em `aberta`, `orcamento_aprovado` e `em_servico`. Orçamento sem valor não pode ser aprovado.
- **Cota mensal:** conta OS criadas no mês corrente em America/Sao_Paulo, incluindo excluídas. `criada_em` é gravado explicitamente em hora local de Brasília para a contagem e a gravação usarem o mesmo referencial.
- **Anexos (MinIO):** bucket **privado e separado** (`MINIO_ANEXOS_BUCKET`, padrão `oficinaos-anexos`), criado sem política. Escolhido em vez de restringir a política do bucket de avatares (que o auth-service define) por ser menos invasivo. Leitura só pela rota do gateway.
- **Perfil:** `GET /api/profile/<id>` era público (vazava nome e e-mail entre oficinas). Agora exige login e só é visível ao próprio usuário, a admin ou à mesma oficina (404 caso contrário).
- **Rota inexistente com POST/DELETE** respondia 405 por causa do catch-all do frontend; agora responde 404 JSON (`serve_frontend` aceita todos os métodos).
- **`mem_limit: 1g`** adicionado a todos os serviços do compose (a confirmar pelo João, conforme o plano).
- **Bucket de avatares:** o padrão passou de `tomhanks-avatars` para `oficinaos-avatars`. Quem já tem avatares no bucket antigo deve manter `MINIO_BUCKET_NAME=tomhanks-avatars` na stack (ver DEPLOY.md).
- **Scripts `demo_logs.sh`, `demo_profile.sh`, `demo_swagger.sh`** removidos (exercitavam favoritos, comentários e catálogo; continuam no histórico do git). A remoção entrou no commit `build(compose)`.
- **Docs históricas:** README (seções 11 em diante) e DOCUMENTACAO.md antigos foram movidos sem alteração de conteúdo para `docs/historico-tomhanks.md` e `docs/historico-documentacao-tomhanks.md`.
- **Dev local:** a porta 3307 e a subnet 10.201.0.0/24 já estavam em uso por outros containers na máquina; o override de dev usa MariaDB em 3398, Prometheus em 9092, Grafana em 3012 e subnet 10.211.0.0/24. Esses containers não foram tocados.
- **Falha minha registrada:** o commit `docs: README e documentação do OficinaOS` foi feito com 1 teste vermelho (`test_legado_removido`, o cenário de aceite citava as palavras do legado de propósito). Corrigido no commit seguinte; a regra é checar o código de saída do `pytest` antes de commitar.
- **Pendente do João:** URL pública (o README tem `URL_NO_AR` como marcador), confirmação do `mem_limit`, passos de `DEPLOY.md`.

## Atividade 11 (desvios e decisões)

- **Tenant da assinatura:** a assinatura é da **oficina** (`assinaturas.oficina_id` único), com `usuario_id` do dono que assinou. O customer da Stripe fica nessa tabela, não no usuário (explicar no relatório).
- **Valor mensal vem do evento da Stripe**, não de constante: `amount_total` no `checkout.session.completed` e preço x quantidade no `customer.subscription.updated`. `PRO_VALOR_CENTAVOS` (4900) é só reserva. Com cupom, o `amount_total` do checkout mostra o valor com desconto até o próximo `subscription.updated`.
- **MRR de teste** soma só `active` e `trialing`. `past_due` continua com acesso Pro, aparece em "inadimplentes" e fica fora do MRR.
- **Plano lido do banco a cada requisição**, via `GET /internal/plano` do payment-service (sem Stripe, sem Redis). Se o payment-service falhar, o gateway assume **Free** (lado seguro: nunca libera o que não foi pago; um dono Pro perde a liberação enquanto o serviço estiver fora).
- **Painel admin em `/app/admin`** (dentro do shell, protegido por papel) em vez de `/admin` solto; passou a ser a página inicial do admin. Dados do painel em `GET /api/admin/painel`, que reúne `/internal/resumo` (payment) e `/internal/usuarios/contagem` (auth). Se payment ou auth falharem, responde 503 em vez de mostrar números inventados.
- **Tela de plano em `/app/plano`**, com `GET /api/plano` (dono e mecânico leem; só o dono gerencia). As URLs de retorno do checkout passaram a `/app/plano?assinatura=ok|cancelada`; em produção precisam ser configuradas na stack (DEPLOY.md, seção 4).
- **Checkout e portal movidos para `backend/dominio.py`** (usam `require_roles('dono')`); saíram do `backend/app.py`. O gateway nunca aceita `oficina_id` do corpo.
- **Entitlement legado removido** (`/entitlement`, `/api/premium/status`, cache Redis e `ENTITLEMENT_CACHE_TTL`). `stripe_customers`/`google_id` só restam na migração do legado.
- **Migração do legado `stripe_customers` → `assinaturas`:** a função `legado_para_assinaturas` existe e é testada, mas **não está ligada ao deploy**: exigiria um mapa `google_id → (oficina, usuário)` do auth-service e o legado é de teste. As oficinas novas partem do Free.
- **Cenário `ativ11.py` com eventos assinados:** com `--webhook-secret` (segredo de TESTE da stack, só pelo terminal) ele simula checkout, falha de pagamento e cancelamento. Não substitui o pagamento com o 4242, feito por `scripts/evidencias/checkout.py`.
- **Descoberta na validação local:** a stack `oficinaos-dev` precisa ser reconstruída com `-p oficinaos-dev` (o nome padrão do projeto cria imagens `oficinaos-*` que a stack não usa).
- **Não verificado nesta máquina:** o checkout real e o portal da Stripe (sem chaves de teste aqui). O cenário os pula com `[SKIP]`; `checkout.py` foi exercitado só até a abertura da Stripe.

## OficinaOS v2: orçamento, link do cliente, catálogo, histórico e pagamento

Pedido do João em 12/11/2026: funcionalidades de gestão de oficina, implementadas por subagentes e revisadas por mim, entrando na entrega da A11.

- **Como foi feito:** a base comum (migração `0003_oficina_v2`, ganchos em `backend/ordens.py`, blueprints e fragmentos de Swagger vazios, esqueleto do frontend) veio primeiro, para os três subagentes trabalharem em paralelo sem mexer nos mesmos arquivos (orçamento; catálogo; histórico e financeiro). Revisei o código de cada um antes de juntar na `main`. Os worktrees nasceram de um commit antigo e cada agente avançou a própria branch com `merge --ff-only`; juntei com fast-forward/cherry-pick, sem reescrever histórico publicado.
- **Orçamento = snapshot dos itens da OS**, sem status "rascunho": os itens da OS já são o rascunho. "Expirado" é calculado pela validade, nunca gravado.
- **Máquina de estados intacta:** `TRANSICOES` não mudou. Com orçamento enviado, a aprovação direta pelo status responde 409; aprovar é pelo orçamento (`transicionar(..., via_orcamento=True)`), com os mesmos eventos. Orçamento cujo subtotal difere do total atual da OS responde 409 ("desatualizado: reenvie"). Recusar mantém a OS aberta.
- **Link público:** o banco guarda só o sha256 do token; o caminho devolvido é relativo (o front monta a URL com a própria origem, sem confiar no `Host`). O limite de tentativas é por IP **e** por token, porque o IP vem de `X-Forwarded-For` e pode ser falsificado. A decisão pelo link entra na auditoria da oficina com um ator sintético (cliente sem id).
- **Anotações são só internas** (sem flag de visível ao cliente); o texto para o cliente é `observacoes_cliente` do orçamento.
- **Catálogo sem coluna na OS:** o "um clique" acontece no navegador, que manda descrição e valor para a rota de itens que já existia.
- **Financeiro em regime de caixa:** o faturado conta o dia do pagamento. O desconto vale do orçamento aprovado (`valor_devido`), e pagamentos não passam do devido (OS travada com `with_for_update`). Entregar sem pagar é permitido ("fiado" vira "a receber").
- **Correção encontrada pelos agentes:** `paraCentavos` transformava "45.90" em 459.000 centavos (removia todos os pontos). Corrigido com teste Vitest.
- **Limite conhecido:** "a receber" e o histórico fazem consultas por OS (N+1). É aceitável no volume de uma oficina pequena; se crescer, vira uma consulta agregada.
