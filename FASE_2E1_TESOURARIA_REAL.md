# Fase 2E.1 — Tesouraria real consolidada

## Natureza da visão

A Tesouraria desta fase é uma projeção de **fluxo de caixa conhecido**. Ela não
é saldo bancário, porque o sistema ainda não possui saldo inicial confirmado,
contas bancárias normalizadas nem conciliação bancária implementada.

Nenhuma tabela de resumo foi criada. A visão é derivada, em leitura, das fontes
reais já existentes.

## Movimentos

- `CONTRIBUTION`: entrada pelo valor original de `funding_contributions`, na
  data do aporte.
- `SALE`: saída única pelo `released_amount` da Venda operacional, na
  `operation_date`. Contratos usam `operational_contracts`; empréstimos órfãos
  usam `operational_loans` e mantêm a identidade `loan:<id>`.
- `REVENUE`: entrada pelo `paid_amount` de `operational_installments`, somente
  quando há `payment_date` e valor recebido positivo.

`funding_allocations`, itens de rateio e `PRINCIPAL_RETURN` não geram movimentos
de Tesouraria. Eles explicam a composição econômica do Funding, mas o caixa já
foi registrado pela Venda ou pela Receita.

Vendas sem data financeira ou sem valor liberado continuam visíveis e são
contabilizadas nos indicadores de dados indisponíveis. Valores inexistentes não
são convertidos silenciosamente em caixa zero.

## Totais

- Entradas: Aportes + Receitas recebidas.
- Saídas: Vendas/liberações com valor conhecido.
- Fluxo líquido conhecido: Entradas − Saídas.

Todos os cálculos monetários usam `Decimal`; juros, allocations, rateios e
retornos internos do Funding não são adicionados novamente.

## API

- `GET /api/treasury/summary`
- `GET /api/treasury/movements`
- `GET /api/treasury/movements/{id}`

Resumo e listagem aceitam período, tipo, busca e investidor. Filtro de conta ou
operador financeiro não é oferecido porque esses campos ainda não existem de
forma confiável na camada normalizada.

O contrato da API já reserva `CAPITAL_REMUNERATION` e os estados de validação
`PENDING`, `VALIDATED` e `DIVERGENT`, sem criar eventos ou valores nesta fase.
