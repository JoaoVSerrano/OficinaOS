# Backlog — OficinaOS

Issues planejadas para as Atividades 10 e 11. Cada uma tem título, descrição curta, critério de aceitação e label sugerida.

## 1. Modelar o domínio e criar `db/001_dominio.sql`
**Label:** `atividade-10`
**Descrição:** Criar as tabelas de oficinas, clientes, veículos, ordens de serviço, itens da OS e anexos, com script SQL e dados de seed.
**Aceite:**
- [ ] `db/001_dominio.sql` cria todas as tabelas com chaves e índices (placa única por oficina).
- [ ] Seed com ao menos 2 oficinas, 3 clientes, 4 veículos e 5 OS fictícias.
- [ ] Toda tabela do domínio tem `oficina_id`.

## 2. Papéis `admin`, `mecanico` e `cliente` no auth-service
**Label:** `atividade-10`
**Descrição:** Substituir `usuario`/`admin` pelos papéis do negócio, com enforcement no backend.
**Aceite:**
- [ ] Papel inválido na mudança de papel retorna 400.
- [ ] `mecanico` não acessa rotas de dono (403); `cliente` só vê as próprias OS.
- [ ] Testes cobrem 401 e 403 por papel.

## 3. API CRUD de ordens de serviço com isolamento por oficina
**Label:** `atividade-10`
**Descrição:** Criar, listar, detalhar, editar e mudar status de OS, sempre filtrando pela oficina do usuário logado.
**Aceite:**
- [ ] Abrir ou editar OS de outra oficina retorna 404 (ou 403) e gera log.
- [ ] Status válidos: aberta, orçamento aprovado, em serviço, pronta, entregue.
- [ ] Rotas documentadas no Swagger e cobertas pelo teste de paridade.

## 4. Eventos de negócio no log-service
**Label:** `atividade-10`
**Descrição:** Registrar `os.aberta`, `os.orcamento_aprovado`, `os.status_alterado` e `os.entregue` (e os 403 do domínio).
**Aceite:**
- [ ] Cada evento aparece no painel de auditoria com usuário, oficina e OS.
- [ ] Nenhum dado pessoal sensível no detalhe do log.

## 5. Upload de fotos da OS no MinIO
**Label:** `atividade-10`
**Descrição:** Anexar fotos de entrada, peças trocadas e comprovantes à OS; o banco guarda só a chave do objeto.
**Aceite:**
- [ ] Aceita PNG/JPG/WEBP até 5 MB; recusa o resto.
- [ ] Só quem pertence à oficina da OS lê ou envia anexos.

## 6. Telas de OS (listar, criar, detalhar, editar)
**Label:** `atividade-10`
**Descrição:** Frontend Angular com linguagem do negócio ("Abrir ordem de serviço", "Aprovar orçamento", "Entregar veículo").
**Aceite:**
- [ ] Fluxo completo de uma OS pela interface, sem usar a API na mão.
- [ ] Nenhum texto de filmes na interface.

## 7. Landing page pública
**Label:** `atividade-10`
**Descrição:** Página com proposta de valor, planos Free e Pro e botão "Criar conta".
**Aceite:**
- [ ] Acessível sem login.
- [ ] Botão leva ao cadastro; a oferta cita Free (20 OS, 1 mecânico) e Pro (R$ 49/mês).

## 8. Remover Tom Hanks, filmes e TMDB
**Label:** `atividade-10`
**Descrição:** Retirar do código, do compose, do `.env.example`, dos testes e da documentação tudo que é do catálogo de filmes, incluindo `TMDB_API_KEY` e `TMDB_LANGUAGE`.
**Aceite:**
- [ ] `grep -ri "tmdb\|tom hanks\|filme"` não encontra nada fora do histórico do git.
- [ ] Testes passam e a stack sobe.

## 9. Apontar o Portainer para o repositório novo
**Label:** `atividade-10`
**Descrição:** Trocar a stack para o repositório OficinaOS (pull + redeploy), mantendo variáveis, subdomínio e limite de 1 GB por container.
**Aceite:**
- [ ] Stack no Portainer usa `JoaoVSerrano/OficinaOS`.
- [ ] Subdomínio e variáveis inalterados; cada container com limite de 1 GB.
- [ ] `/health` responde 200 após o deploy; webhook do Actions funciona.

## 10. Plano Pro no Stripe, limites por plano e painel de MRR
**Label:** `atividade-11`
**Descrição:** Assinatura recorrente de R$ 49/mês (modo de teste), limites do Free aplicados na API e painel admin com MRR de teste.
**Aceite:**
- [ ] Oficina Free bloqueada na 21ª OS do mês e no 2º mecânico (402).
- [ ] Webhook com assinatura validada e eventos idempotentes.
- [ ] Painel mostra assinantes Pro e MRR de teste; nenhum dado de cartão é guardado.
