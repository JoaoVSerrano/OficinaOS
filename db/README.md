# Banco de dados do OficinaOS

Quem clonar o repositório consegue recriar o banco do domínio em um MariaDB vazio.

| Arquivo | O que faz |
|---|---|
| `001_dominio.sql` | Esquema: `oficinas`, `clientes`, `veiculos`, `ordens_servico`, `itens_os`, `anexos_os` (com chaves estrangeiras). Gerado das migrações Alembic por `scripts/export_sql.sh`. |
| `002_seed.sql` | Dados fictícios: 2 oficinas, 3 clientes, 4 veículos, 5 ordens de serviço. Idempotente (`INSERT IGNORE`); pode ser reaplicado. **Não cria login nem senha.** |

## Recriar o banco

```bash
mariadb -u USUARIO -p NOME_DO_BANCO < db/001_dominio.sql
mariadb -u USUARIO -p NOME_DO_BANCO < db/002_seed.sql
```

Alternativa (como o sistema faz sozinho ao subir): `alembic -c alembic.ini upgrade head`
(gateway) e `alembic-auth.ini` / `alembic-payment.ini` para auth e pagamento.

## Atenção

`001_dominio.sql` remove `favoritos` e `comentarios` (domínio antigo do projeto) se existirem.
As tabelas de usuários (`usuarios`) e de assinaturas (`assinaturas`) pertencem ao auth-service e ao
payment-service e são criadas pelas migrações deles. `usuario_id`/`mecanico_id` apontam para
`usuarios.id` sem chave estrangeira, porque os serviços têm migrações independentes.

Regerar o esquema: `./scripts/export_sql.sh`.
