# Instruções do projeto

Leia `PLANO_SISTEMA_FUNDING_REMO.md` antes de alterar o sistema.

## Regras obrigatórias

- Use Python 3.12 no backend.
- Use FastAPI, Pydantic, SQLAlchemy 2 assíncrono, asyncpg e Alembic.
- O PostgreSQL é gerenciado no Supabase.
- Leia `DATABASE_URL` exclusivamente do ambiente ou do `.env` local.
- Leia `OPERATIONAL_EXCEL_PATH` exclusivamente do ambiente ou do `.env` local.
- Nunca coloque credenciais no código, frontend, logs ou Git.
- Nunca coloque o caminho operacional real em código, documentação, logs ou
  Git.
- Somente o backend acessa o PostgreSQL.
- O arquivo Cadastro de Clientes é a fonte da verdade para clientes,
  contratos, empréstimos, amortizações e demais dados operacionais existentes.
- O PostgreSQL Supabase é a fonte da verdade para investidores canônicos,
  aportes, alocações, remunerações, PJR, reinvestimentos e movimentos de
  tesouraria do novo sistema.
- `Funding Remo.xlsm` é somente referência do modelo legado e reconciliação.
  Nunca importe, espelhe ou sincronize esse arquivo.
- Nunca escreva no Excel operacional. Sempre copie o Cadastro de Clientes para
  uma área temporária antes de ler.
- Preserve a interface plugável `FileSource`.
- Use `Decimal` e `NUMERIC(14,2)` para dinheiro; nunca float.
- Dados inválidos devem virar inconsistências, não interromper lotes válidos.
- Não antecipe funcionalidades de fases posteriores.
- Em Windows, documente comandos compatíveis com CMD.

## Fontes oficiais

1. Cadastro de Clientes: fonte operacional para o espelho de clientes,
   contratos, empréstimos e amortizações.
2. PostgreSQL Supabase: fonte dos dados próprios do novo módulo de funding.
3. Funding Remo.xlsm: referência legada, sem fluxo de importação.

## Estado atual

A Fase 0, o diagnóstico técnico da Fase 1A e a Fase 1B estão concluídos. Duas
sincronizações reais controladas foram executadas. O batch 1 é evidência
imutável e o batch 2 é a referência operacional aprovada. O frontend permanece
integralmente mockado.

Qualquer nova sincronização do arquivo operacional real continua bloqueada até
autorização expressa específica. Não execute
`sync-operational-excel` contra o arquivo configurado sem essa autorização.

A migration `f1c000000001` foi aplicada e o batch 2 foi promovido como promoção
1. Vendas e Receita usam a API operacional real, paginada e sem fallback para
mocks. Funding, investidores, capital REMO e validação bancária continuam sem
dados reais e não podem ser associados aos contratos operacionais. Não abra
novamente o Excel, não use `--force` e não execute outra sincronização ou
promoção sem nova autorização expressa.
