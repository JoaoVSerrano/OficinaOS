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
