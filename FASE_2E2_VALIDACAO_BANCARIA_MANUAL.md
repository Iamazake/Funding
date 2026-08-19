# Fase 2E.2 — Validação bancária manual da Tesouraria

## Escopo

A validação bancária é uma camada de conferência e auditoria sobre os movimentos
derivados da Tesouraria. Ela não materializa os movimentos, não altera suas
fontes e não executa conciliação ou correção automática.

As identidades estáveis reutilizadas são:

- `contribution:<uuid>` para aportes;
- `sale:contract:<id>` para vendas promovidas a contrato;
- `sale:loan:<id>` para empréstimos sem contrato promovido;
- `revenue:<id>` para receitas pagas.

## Persistência e estados

A migration `f2e200000001` cria somente
`treasury_bank_validations`, sem inserir registros e sem backfill. Cada linha é
uma versão imutável da conferência, com `version`, `is_current` e
`supersedes_validation_id`. A restrição parcial exclusiva por `movement_key`
garante no máximo uma versão atual.

`PENDING` não é persistido: ele é derivado quando o `LEFT JOIN` não encontra
uma validação atual. As linhas persistidas têm um destes resultados, calculados
no backend com `Decimal` e arredondamento `ROUND_HALF_UP`:

- `VALIDATED`: valor observado igual ao snapshot do sistema;
- `DIVERGENT`: valor observado diferente, com justificativa obrigatória.

A diferença é `observed_amount - system_amount_snapshot`. O usuário sempre
informa valor positivo; entrada ou saída vem do movimento derivado.

Cada versão guarda os snapshots de valor, data, tipo e direção do movimento,
além de valor/data observados, diferença, referência bancária opcional,
justificativa e timestamps. A data bancária permanece separada da data
operacional. Como ainda não existe autenticação confiável, `validated_by` fica
preparado e nulo; nenhum ator é inventado.

Correções criam uma nova versão e preservam as anteriores no histórico. A
gravação usa transação, advisory lock por movimento, bloqueio da versão atual e
constraints de unicidade/coerência. Um movimento inexistente é rejeitado.

## API e consultas

- `GET /api/treasury/summary`
- `GET /api/treasury/movements`
- `GET /api/treasury/movements/{movement_id}`
- `GET /api/treasury/movements/{movement_id}/validation`
- `POST /api/treasury/movements/{movement_id}/validation`
- `GET /api/treasury/movements/{movement_id}/validation-history`

O POST recebe somente valor/data observados, referência bancária e justificativa.
O backend resolve novamente o movimento e produz o snapshot, a diferença e o
status. Listagem e resumo usam uma união SQL das fontes, um único join com a
validação atual e filtros SQL por período, tipo, busca, investidor e validação
antes da paginação, sem N+1 e sem carregar toda a Tesouraria em memória.

## Interface

A Tesouraria mostra badges Pendente, Validado e Divergente, filtro combinável,
indicadores de quantidade e diferença líquida, e uma coluna de validação. O
modal apresenta direção, valor/data do sistema, valor/data do banco, referência
opcional, justificativa, diferença e resultado calculados enquanto o usuário
digita, além do histórico de versões. Não há bancos fictícios, mocks nem
persistência em `localStorage`.

## Integridade das fontes

A migration não modifica aportes, vendas, receitas, allocations, ledger ou
distributions. Não foram executados sincronização Excel, promoção operacional,
backfill financeiro ou criação de validações pendentes. A validação divergente
registra a diferença, mas nunca corrige automaticamente a origem.
