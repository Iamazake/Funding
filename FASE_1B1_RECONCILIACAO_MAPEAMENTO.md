# Fase 1B.1 — Reconciliação do mapeamento

> Análise concluída exclusivamente sobre o batch 1 já persistido no espelho do
> Supabase. O Excel não foi aberto, nenhuma linha foi alterada e nenhuma nova
> sincronização foi executada.

## 1. `ECON_AMORTIZACOES.BAIXA _TOTAL`

Foram analisadas as 12.120 linhas persistidas:

| Evidência | Quantidade |
|---|---:|
| `NULL`/vazio | 807 |
| texto | 11.313 |
| valores distintos, incluindo `NULL` | 3 |
| marcador `S` | 11.312 |
| marcador `I` | 1 |
| booleano, data ou número | 0 |

O campo não possui semântica monetária. Ele é um marcador textual ligado a
pagamento parcial da parcela. A classificação recomendada é **STATUS/TEXT**,
preservada sem interpretação até que o domínio de movimentos de pagamento seja
implementado.

Decisão posterior confirmada pela REMO: **Pagamento parcial previsto para etapa
futura.** O campo não deve passar pelo parser de dinheiro nem tornar a linha
inválida.

## 2. Precisão monetária de origem

As 578 ocorrências foram analisadas sem arredondamento ou alteração do batch:

| Campo | Casos | Escala mínima | Escala máxima | Frequência por escala | Maior diferença para centavos |
|---|---:|---:|---:|---|---:|
| `VAL_AMTZ_JUR` | 235 | 3 | 15 | 3: 51; 11: 1; 12: 2; 13: 37; 14: 104; 15: 40 | 0,005 |
| `VAL_AMTZ_PRINC` | 175 | 3 | 15 | 3: 66; 11: 1; 12: 9; 13: 40; 14: 54; 15: 5 | 0,005 |
| `DESCONTO_CONC` | 81 | 3 | 16 | 3: 6; 12: 2; 13: 21; 14: 43; 15: 8; 16: 1 | 0,005 |
| `VAL_PGTO` | 81 | 11 | 15 | 11: 1; 12: 4; 13: 25; 14: 45; 15: 6 | 0,00486439977811 |
| `VAL_PARCELA` | 6 | 13 | 14 | 13: 1; 14: 5 | 0,0000000000001 |

Todos os 578 valores mudariam ao serem arredondados para centavos. As escalas
de 11 a 16 casas são compatíveis com resultados de fórmula ou artefatos da
representação numérica do Excel; os casos de escala 3 podem conter precisão de
cálculo intencional. A diferença individual é limitada a meio centavo.

Política confirmada:

1. **Precisão de origem:** preservar exatamente em `raw_data` para auditoria.
2. **Valor operacional:** converter com `Decimal` e armazenar em centavos.
3. **Arredondamento:** `ROUND_HALF_UP` para duas casas decimais.
4. **Severidade:** o arredondamento não gera divergência operacional nem torna
   a linha inválida.

## 3. Colisões de amortização

Cada um dos quatro grupos contém duas linhas distintas:

| Grupo mascarado | Linhas | `CHAVE` distintas | Vencimentos distintos | Datas de baixa distintas | Status distintos | Valores de parcela distintos | Valores pagos distintos |
|---|---:|---:|---:|---:|---:|---:|---:|
| Grupo 1 | 2 | 2 | 2 | 2 | 1 | 2 | 2 |
| Grupo 2 | 2 | 2 | 1 | 2 | 1 | 2 | 2 |
| Grupo 3 | 2 | 2 | 2 | 2 | 1 | 2 | 2 |
| Grupo 4 | 2 | 2 | 1 | 2 | 2 | 2 | 2 |

As oito linhas possuem hashes de origem distintos. A evidência é compatível
com eventos de pagamento parcial, não com duplicação silenciosa.

- `COD_CONTRATO + COD_PARCELA` não é único.
- Acrescentar `VENCIMENTO` ainda não resolve os grupos 2 e 4.
- `CHAVE` diferencia as ocorrências observadas, mas é calculada e não deve ser
  adotada como identificador definitivo sem contrato de negócio.
- No espelho, `import_batch_id + source_row_number` continua sendo identidade
  técnica segura.
- No domínio futuro, a identidade deve separar **parcela** de **movimento de
  pagamento**, mantendo relação 1:N.

## 4. Matriz proposta de severidade

| Situação | Severidade proposta |
|---|---|
| Linha íntegra | `VALID` |
| CPF inválido ou data secundária inválida | `WARNING` |
| Campo monetário secundário não interpretável | `WARNING` |
| Empréstimo ou amortização órfã | `DIVERGENT` |
| Múltiplos movimentos da mesma parcela | informação; linha permanece `VALID` |
| Precisão monetária arredondada | auditoria técnica; linha permanece `VALID` |
| Identificador operacional essencial ausente | `INVALID` |
| Valor monetário essencial impossível de interpretar | `INVALID` |
| Aba/coluna obrigatória ausente ou esquema incompatível | falha estrutural do lote |

Estimativa do batch 1 com a matriz confirmada, sem alterar os registros:

| Aba | Valid | Warning | Divergent | Invalid |
|---|---:|---:|---:|---:|
| `BCLI_CADASTRO` | 1.419 | 40 | 0 | 0 |
| `DFEN_CONTRATO` | 1.452 | 4 | 0 | 0 |
| `ECON_EMPRESTIMOS` | 1.429 | 4 | 3 | 0 |
| `ECON_AMORTIZACOES` | 12.068 | 38 | 14 | 0 |
| **Total** | **16.368** | **82** | **17** | **0** |

Os 11.362 `INVALID` originais de `ECON_AMORTIZACOES` desaparecem na simulação:
`BAIXA _TOTAL` deixa de ser dinheiro, 578 precisões são arredondadas, quatro
colisões viram informação, órfãos viram divergência e campos secundários viram
warning. As categorias podem se sobrepor na mesma linha.

## 5. Datas inválidas

As 40 ocorrências pertencem a `BCLI_CADASTRO.DT_NASC`:

| Padrão | Quantidade |
|---|---:|
| texto com formato brasileiro, mas data não reconhecida | 29 |
| outro texto | 11 |

Nenhum valor pessoal foi incluído nesta análise. `DT_NASC` é estruturalmente
esperada, mas seu conteúdo não é necessário para preservar a linha bruta e seu
código; portanto, uma data inválida deve resultar em `WARNING`, com o valor
original preservado e a data normalizada nula. Datas ligadas a pagamento ou
operação também podem ser warning quando contrato e parcela continuarem
identificáveis. A ausência dos identificadores essenciais permanece `INVALID`.

## 6. Órfãos

| Relação | Linhas | Contratos distintos |
|---|---:|---:|
| Empréstimos sem `DFEN_CONTRATO` | 3 | 3 |
| Amortizações sem `DFEN_CONTRATO` | 12 | 1 |
| Amortizações sem `ECON_EMPRESTIMOS` | 14 | 3 |

As 12 amortizações sem DFEN estão contidas no grupo sem empréstimo. As duas
linhas adicionais referenciam contratos existentes em `DFEN_CONTRATO`, mas
ausentes em `ECON_EMPRESTIMOS`. Todos devem permanecer no espelho como
`DIVERGENT`, sem correção automática.

## 7. Timestamps

A causa da duração inconsistente foi a mistura de relógios:

- `started_at` de runs e batches vinha de `server_default=now()` no Supabase;
- `finished_at`/`completed_at` vinha de `datetime.now(UTC)` na aplicação.

Embora as colunas já sejam `TIMESTAMP WITH TIME ZONE`, relógios físicos com
pequeno desvio produziram um batch cujo término apareceu anterior ao início.

Alterações necessárias em etapa posterior:

- preencher `sync_runs.started_at`, `sync_runs.finished_at`,
  `operational_import_batches.started_at` e `completed_at` com datetimes UTC da
  mesma camada;
- manter `DateTime(timezone=True)`/`TIMESTAMP WITH TIME ZONE`;
- acrescentar `duration_ms` a runs e batches;
- calcular duração com relógio monotônico, nunca pela subtração entre relógios
  da aplicação e do banco;
- manter `created_at` e `imported_at` timezone-aware;
- converter para `America/Sao_Paulo` somente na futura apresentação.

## 8. Decisões ainda necessárias

- significado formal de cada marcador de `BAIXA _TOTAL`, especialmente `I`;
- identificador canônico futuro do movimento de pagamento;
- regra de composição entre parcela e vários movimentos;
- quais valores monetários são essenciais para uso operacional, além dos
  mínimos atualmente adotados;
- destino futuro da auditoria técnica de arredondamento;
- política de exibição de timestamps e duração no frontend futuro.

## 9. Alterações técnicas posteriores indicadas

- retirar `BAIXA _TOTAL` do parser monetário e guardar seu marcador original;
- implementar função central `Decimal` com `ROUND_HALF_UP`;
- adicionar severidade `info`, `warning`, `divergent` ou `invalid` às
  inconsistências futuras;
- não criar restrição única em contrato + parcela;
- adicionar colunas de duração monotônica e padronizar timestamps UTC em nova
  migration, sem editar a migration já aplicada;
- manter o batch 1 imutável e aplicar as regras somente em sincronização futura
  expressamente autorizada.
