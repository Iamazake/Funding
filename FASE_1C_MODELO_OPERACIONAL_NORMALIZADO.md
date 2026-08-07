# Fase 1C — proposta da camada operacional normalizada

## Estado e limite desta entrega

A implementação, a migration e o comando de promoção estão preparados e
testados somente com dados sintéticos. A migration `f1c000000001` **não foi
aplicada** e o batch 2 **não foi promovido**. O Excel não foi aberto e nenhuma
sincronização foi executada.

O fluxo proposto é:

```text
operational_import_batch sucedido
  -> espelhos excel_* imutáveis
  -> promoção explícita e transacional
  -> snapshot operacional normalizado
  -> services/repositories da futura API
  -> Vendas e Receita
  -> composição separada do domínio Funding
```

## Modelo e relacionamentos

### `operational_promotions`

Registra qual batch gerou cada snapshot normalizado. `source_batch_id` é único,
o que torna a promoção idempotente. Somente uma promoção pode ter
`is_current = true`. O resumo contém contagens, qualidade, diferenças agregadas
DFEN/ECON e grupos candidatos de parcela.

Uma promoção futura torna apenas a promoção anterior não atual. Seus clientes,
contratos, empréstimos, parcelas, vínculos de qualidade e referências de origem
continuam imutáveis.

### `operational_clients`

Uma linha do BCLI gera uma linha operacional. Não há unicidade nem fusão por CPF
ou código de cliente. Duplicidades são preservadas como identidades distintas e
recebem `WARNING`. CPF inválido permanece com `cpf_original`,
`cpf_normalized = NULL` e qualidade `WARNING`.

Um contrato ou empréstimo só recebe `client_id` quando código/CPF oferecem um
candidato inequívoco. Relações ambíguas ficam nulas e ganham um evento de
qualidade, sem escolha silenciosa.

### `operational_contracts`

É a representação oficial do contrato de crédito e tem DFEN_CONTRATO como fonte
primária. `contract_code` é único dentro do batch normalizado. Guarda cliente
quando resolvido, datas, prazo e valores contratuais. O status é complementado
por ECON_EMPRESTIMOS quando existe correspondência inequívoca por contrato.

Não contém investidores, capital REMO, aportes, fontes ou rateio.

### `operational_loans`

Permanece separado. Conserva cada linha de ECON_EMPRESTIMOS, inclusive os três
órfãos, com `contract_id = NULL` e `DIVERGENT`. Também conserva as taxas e o
status que não existem em DFEN.

Essa decisão evita esconder divergências ou transformar duas fontes quase 1:1
em uma entidade única antes de existir uma regra oficial de precedência para
todos os atributos.

### `operational_installments`

Cada linha de ECON_AMORTIZACOES gera uma observação de parcela. Não existe
restrição única em `contract_code + installment_code`. Todos os registros são
preservados.

`candidate_group_key` e `candidate_group_size` apenas indicam linhas que podem
ser analisadas juntas; não consolidam, somam nem deduplicam. A linha mantém FK
direta para o espelho, valores normalizados e os originais ambíguos necessários.

### `operational_payment_movements`

Prepara a relação parcela 1:N movimentos. A FK `installment_id` não é única e
cada movimento exige referência à linha de amortização que o originou.

A promoção inicial não materializa movimentos automaticamente. Ainda não há
regra suficiente para decidir com segurança se toda linha é parcela, movimento
ou ambos. `S` e `I` permanecem em `payment_marker_original`; nenhum significado
é atribuído a `I`.

### `operational_quality_links`

Liga exatamente um registro normalizado a uma inconsistência existente da
sincronização ou a um evento novo e pequeno da normalização, como identidade de
cliente ambígua. Quando a inconsistência já existe, somente seu ID é
referenciado; mensagem, valor e evento não são copiados.

O caminho auditável fica:

```text
registro operacional
  -> operational_quality_links
  -> data_inconsistencies
  -> source_sheet + source_row_number
  -> linha excel_* referenciada pelo registro
  -> operational_import_batch
  -> sync_run/origem
```

## DFEN_CONTRATO × ECON_EMPRESTIMOS

| Atributo normalizado | Fonte oficial no contrato | Campo ECON preservado no empréstimo |
|---|---|---|
| cliente | DFEN `COD_CLIENTE`/`NUM_CPF` | ECON `COD_CLIENTE`/`NUM_CPF` |
| data da operação | DFEN `DT_OPERACAO` | ECON `DT_OPERACAO` |
| primeiro vencimento | DFEN `VCTO_PRIM_PARC` | ECON `VENCIMENTO1` |
| prazo | DFEN `PRAZO` | ECON `PRAZO_PGTO` |
| principal | DFEN `PRINCIPAL` | ECON `VL_PRINCIPAL` |
| IOF | DFEN `IOF` | ECON `IOF` |
| financiado | DFEN `VL_FINANCIADO` | ECON `VL_FINACIADO` |
| parcela/PMT | DFEN `PMT` | ECON `PMT` |
| liberado | DFEN `VL_LIBERADO` | ECON `VL_LIBERADO` |
| taxa de juros/TIR/CET | não existe em DFEN | somente ECON |
| status | complementado por ECON | somente ECON |

A promoção compara os dez campos equivalentes e grava no resumo somente a
quantidade de diferenças por campo. Os valores permanecem em suas entidades e
linhas de origem, sem cópia em JSON de comparação. A contagem real será
produzida somente quando o batch 2 for promovido após autorização.

## Dinheiro e qualidade

- dinheiro: Python `Decimal`, PostgreSQL `NUMERIC(14,2)`;
- arredondamento defensivo: `ROUND_HALF_UP` para centavos;
- taxas: `NUMERIC(18,10)`;
- nenhum cálculo usa `float`;
- valor monetário ambíguo: normalizado `NULL`, original preservado e `WARNING`;
- estados permitidos: `VALID`, `WARNING`, `DIVERGENT`, `INVALID`;
- `INVALID` permanece reservado a registro essencialmente inutilizável.

Os 18 `DESCONTO_CONC` e oito `VL_LIBERADO` ambíguos não são inferidos. A
rastreabilidade alcança o valor original autorizado no espelho; campos
`*_original` também deixam explícita a situação na camada normalizada.

## Promoção e histórico

Comando preparado, mas ainda não executado:

```cmd
backend\.venv\Scripts\python.exe -m app.cli promote-operational-batch 2
```

O batch é sempre obrigatório e explícito. O serviço:

1. rejeita batch inexistente ou não sucedido;
2. retorna o resultado existente se o batch já tiver sido promovido;
3. lê exclusivamente as quatro tabelas-espelho daquele batch;
4. constrói clientes, contratos, empréstimos e parcelas em memória;
5. persiste promoção, registros e vínculos em uma única transação;
6. reverte tudo se qualquer gravação falhar;
7. mantém snapshots anteriores e suas linhas de origem.

`current_source_batch_id`, `first_seen_batch_id`, `last_seen_batch_id` e
`active_in_source` estão presentes. Nesta primeira materialização, os três IDs
apontam para o mesmo batch. A comparação batch 3 → batch 2, a continuidade de
identidades e a detecção de desaparecimentos ficam para a etapa futura; nenhum
registro será apagado apenas por não reaparecer.

## Mapeamento futuro para Vendas

Vendas consumirá um serviço que combina, sem misturar domínios:

- `operational_contracts`: contrato, cliente, data, prazo, principal, IOF,
  financiado, PMT, liberado;
- `operational_loans`: taxas e status ECON, além de divergências de origem;
- domínio Funding separado: investidores, aportes, capital REMO, fontes,
  rateio, validação da saída e divergências de funding.

## Mapeamento futuro para Receita

Receita consumirá:

- `operational_installments`: contrato, cliente via contrato, parcela,
  vencimento, valor esperado, principal, juros, pago, desconto, status e
  situação;
- `operational_payment_movements`: movimentos 1:N quando a regra de separação
  for aprovada;
- domínio Funding separado: rateio por investidor, validação bancária,
  conciliação e divergências financeiras.

## Índices principais

- promoção por batch, status e promoção atual;
- clientes por código, CPF e linha BCLI;
- contratos por código, cliente, CPF, batch e linha DFEN;
- empréstimos por contrato, cliente e linha ECON;
- parcelas por contrato, código da parcela, grupo candidato e linha de origem;
- movimentos por parcela e linha de origem;
- qualidade por promoção, inconsistência e cada tipo de entidade.

## Riscos e questões abertas

1. A continuidade de um cliente entre batches não pode usar CPF/código como
   identidade única enquanto as ambiguidades não forem resolvidas.
2. A regra para converter observações de amortização em parcela canônica e
   movimentos ainda precisa de validação operacional.
3. O significado de `I` continua deliberadamente desconhecido.
4. Diferenças DFEN/ECON serão quantificadas na promoção real; nenhuma origem
   alternativa será escolhida automaticamente.
5. A política de registros que deixam de aparecer em batches futuros precisa
   distinguir ausência temporária de encerramento real.
6. A futura API deve consultar apenas a promoção atual e nunca expor CPF
   original, nomes ou linhas `excel_*` sem regras de segurança e autorização.

## Migration proposta

- revisão: `f1c000000001`;
- anterior: `ecacd0239c1a`;
- cria somente as oito tabelas normalizadas e seus índices/FKs/checks;
- não altera migrations anteriores;
- não contém carga, promoção ou leitura de Excel;
- compilada com sucesso em modo SQL offline;
- aguarda autorização expressa para aplicação no Supabase.
