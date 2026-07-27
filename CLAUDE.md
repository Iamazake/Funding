# Instruções do projeto

Leia `PLANO_SISTEMA_FUNDING_REMO.md` antes de alterar o sistema.

## Regras obrigatórias

- Use Python 3.12 no backend.
- Use FastAPI, Pydantic, SQLAlchemy 2 assíncrono, asyncpg e Alembic.
- O PostgreSQL é gerenciado no Supabase.
- Leia `DATABASE_URL` exclusivamente do ambiente ou do `.env` local.
- Nunca coloque credenciais no código, frontend, logs ou Git.
- Somente o backend acessa o PostgreSQL.
- Nunca escreva no Excel; ele é a fonte da verdade.
- Preserve a interface plugável `FileSource`.
- Use `Decimal` e `NUMERIC(14,2)` para dinheiro; nunca float.
- Dados inválidos devem virar inconsistências, não interromper lotes válidos.
- Não antecipe funcionalidades de fases posteriores.
- Em Windows, documente comandos compatíveis com CMD.

## Estado atual

Somente a Fase 0 está autorizada: fundação do backend e frontend, configuração
do banco remoto, migration baseline e `GET /health`.

