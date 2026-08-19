# Remo Funding — protótipo funcional de domínio

Aplicação React 18 + TypeScript com backend FastAPI e PostgreSQL Supabase.
Investidores e aportes usam exclusivamente a API real; as áreas de funding de
fases posteriores que ainda forem demonstrativas permanecem isoladas no
repositório local até sua migração específica.

No ambiente local, o backend aceita CORS explicitamente de
`http://localhost:5173` e `http://127.0.0.1:5173`. Em produção, defina
`APP_ENV=production` e informe somente as origins autorizadas em
`CORS_ALLOWED_ORIGINS`, separadas por vírgula. Origins locais não são herdadas
em produção. Credenciais CORS são habilitadas somente para essa lista explícita;
origins curinga não são utilizadas.

O frontend usa `/api` no mesmo origin por padrão. Em desenvolvimento, o proxy
do Vite encaminha `/api` e `/health` para `http://localhost:8000`, preservando
o login local sem CORS. `VITE_API_URL` só deve ser definido quando houver uma
arquitetura deliberadamente separada por origins.

O estado operacional oficial é a promotion #2 / batch #3, com 1.528 Vendas e
12.866 Receitas. O runbook de homologação/produção, backup, migrations e
roteamento está em `FASE_3A_HARDENING_DEPLOY.md`.

Para viabilizar testes locais com contratos operacionais anteriores à data do
aporte, desenvolvimento usa o saldo atual como limite da alocação do
investidor. O ledger preserva a data original da Venda e registra o override na
auditoria. Produção continua usando obrigatoriamente o saldo histórico; o modo
local também pode ser desligado com
`FUNDING_ALLOW_HISTORICAL_ALLOCATION_FOR_TESTS=false`.

### Convenção da taxa contratual

A taxa mensal de `funding_contributions.monthly_rate` é uma fração decimal em
`NUMERIC(12,10)`: **2% a.m. é armazenado como `0.0200000000`**. A API recebe e
devolve strings decimais, e nenhum cálculo financeiro usa `float`.

O valor original do aporte usa `NUMERIC(14,2)`. Correções anteriores à primeira
movimentação atualizam `updated_at` e geram um evento em
`funding_audit_events`. A futura transação que criar a primeira movimentação
deverá preencher `original_amount_locked_at`; depois disso a API rejeita
sobrescrita direta e uma correção terá de ser registrada como evento.

## Separação de domínio

- **Contrato** registra a operação de crédito e sua composição histórica de
  funding. Criar ou liberar um contrato não cria entrada de caixa.
- **Entrada esperada** representa uma parcela/PMT informada por uma baixa
  operacional. A baixa fica pendente até a conferência manual no banco.
- **Receita** é uma projeção analítica dessa mesma entrada: mostra parcela,
  componentes, referências, divergências e rateio histórico. Não cria uma
  segunda entidade nem uma segunda entrada de caixa.
- **Saída** registra desembolsos reais. A liberação do empréstimo é
  `LOAN_RELEASE`, sempre em Tesouraria > Saídas.

O fluxo demonstrativo de uma entrada é: baixa operacional → entrada esperada →
conferência bancária manual → conciliação → divergência ou validação → rateio do
recebimento. A conciliação aceita relações N:N, pagamentos parciais, estornos e
mantém o histórico das associações.

O identificador de `TreasuryIncomingReceipt` é o identificador central também
usado pela Receita, pelo contrato e pelo investidor. Uma alteração na validação
bancária aparece imediatamente nas duas visões.

## Escopo implementado

- investidores e múltiplos aportes por investidor;
- remuneração mensal sobre o valor originalmente aportado;
- contratos com composição ilimitada de fontes, inclusive capital próprio REMO;
- versões históricas de alocações e divergências de funding;
- entradas esperadas com componentes de principal, juros, IOF, multa, desconto
  e prejuízo;
- conferência bancária exclusivamente manual;
- uma ou várias entradas associadas a um ou vários movimentos bancários;
- divergências por diferença de valor ou movimento não encontrado;
- módulo Receita com recebimentos, pendências, divergências, resumo mensal,
  gráficos, filtros e colunas configuráveis;
- total apurado por principal + juros + IOF + multa − desconto − prejuízo;
- rateio por fonte usando `bigint` em centavos, soma exata e maiores restos com
  critério determinístico;
- armazenamento demonstrativo v4, com migração segura dos estados v1, v2 e v3 e
  restauração dos mocks.

O rateio usa a composição de funding válida na data da baixa operacional; na
ausência dela, usa a data de vencimento. Assim, uma correção posterior do
contrato não altera o rateio histórico. Principal, juros e IOF permanecem no
mesmo recebimento operacional e geram somente uma entrada real de caixa por
movimento bancário.

O IOF aparece separadamente, mas não é atribuído automaticamente a investidores
ou ao capital próprio REMO enquanto a regra definitiva não estiver aprovada.

## Rotas

```text
/dashboard
/cadastro/investidores
/cadastro/investidores/:id
/cadastro/aportes
/cadastro/aportes/:id
/cadastro/remuneracoes
/cadastro/remuneracoes/:id
/contratos
/contratos/:id
/contratos/:id/funding
/contratos/composicao
/contratos/alocacoes
/contratos/divergencias
/receita
/receita/:id
/receita/pendencias
/receita/divergencias
/receita/resumo-mensal
/tesouraria
/tesouraria/entradas
/tesouraria/entradas/:id
/tesouraria/saidas
/tesouraria/remuneracoes
/tesouraria/conciliacao
/tesouraria/divergencias
/relatorios
/sincronizacao
/configuracoes
```

As rotas aposentadas de `/vendas` redirecionam sem links quebrados:
`/vendas` e `/vendas/validacao-bancaria` vão para `/tesouraria/entradas`;
`/vendas/divergencias` vai para `/tesouraria/divergencias`; e um antigo
`/vendas/:id` tenta preservar o identificador em `/contratos/:id`.

## Regras monetárias demonstrativas

Valores monetários são strings inteiras de centavos. Cálculos usam `bigint`,
sem ponto flutuante. A distribuição proporcional usa maiores restos; empates
são resolvidos pela ordem estável das alocações, garantindo resultado
reproduzível e soma exata.

O total apurado da Receita é:

```text
principal + juros + IOF + multa - desconto - prejuízo
```

Diferenças em relação ao valor pago são preservadas como divergências; os
componentes operacionais nunca são ajustados silenciosamente para fechar a soma.

A política definitiva de remuneração, PJR e rateio ainda depende de validação do
backend. O capital próprio REMO é uma fonte própria, nunca um investidor
fictício.

## Integração operacional

A Fase 1B adicionou o conector local e o espelho bruto no Supabase. Duas cargas
reais controladas foram concluídas; o batch 1 permanece como evidência do
primeiro importador e o batch 2 é a referência operacional aprovada. O fluxo
sempre cria uma cópia binária temporária
única e abre somente essa cópia, em modo somente leitura. A lista positiva é
restrita a `BCLI_CADASTRO`, `DFEN_CONTRATO`, `ECON_EMPRESTIMOS` e
`ECON_AMORTIZACOES`; abas sensíveis e qualquer outra aba são bloqueadas.

O comando preparado, compatível com o Prompt de Comando do Windows, é:

```cmd
backend\.venv\Scripts\python.exe -m app.cli sync-operational-excel
```

O mesmo hash não é reprocessado por padrão. O uso de `--force` exige uma ação
explícita. Nenhuma nova sincronização está autorizada.

### Regras preparadas após a reconciliação do batch 1

- `BAIXA _TOTAL` é um marcador ligado a pagamento parcial, não dinheiro:
  **Pagamento parcial previsto para etapa futura.**
- valores monetários usam `Decimal` e arredondamento `ROUND_HALF_UP` para
  centavos, preservando a precisão original em `raw_data`;
- CPF e datas secundárias inválidas geram `WARNING`;
- órfãos geram `DIVERGENT`;
- múltiplos movimentos da mesma parcela são preservados como informação;
- `INVALID` fica reservado a identificadores ou valores essenciais inutilizáveis;
- duração usa relógio monotônico e timestamps futuros são enviados em UTC.

Essas regras valem para sincronizações futuras. O batch 1 não foi reprocessado
nem reclassificado. Consulte `FASE_1B1_RECONCILIACAO_MAPEAMENTO.md`.

### Camada operacional normalizada proposta

A Fase 1C prepara snapshots normalizados de clientes, contratos, empréstimos e
parcelas, com rastreabilidade até o espelho e sem deduplicação agressiva. O
comando exige batch explícito:

```cmd
backend\.venv\Scripts\python.exe -m app.cli promote-operational-batch 2
```

Esse comando ainda **não foi executado**. A migration `f1c000000001` também não
foi aplicada e ambos aguardam autorização expressa. Consulte
`FASE_1C_MODELO_OPERACIONAL_NORMALIZADO.md`.

### API operacional e telas reais

A promoção 1 do batch 2 alimenta endpoints paginados de leitura:

```text
GET /api/operational/sales
GET /api/operational/sales/{id}
GET /api/operational/revenue
GET /api/operational/revenue/{id}
```

Vendas e Receita consomem exclusivamente esses DTOs no modo normal. Não existe
fallback silencioso para mocks. CPF, `raw_data`, hashes e modelos SQLAlchemy não
são expostos. Funding, investidores, capital REMO e validação bancária aparecem
como não informados enquanto não houver dados reais desses domínios.

### Funding real da Venda (Fase 2B)

Cada Venda é referenciada pela identidade estável já exposta pela API
operacional: `contract:<id>` para contratos e `loan:<id>` para os empréstimos
órfãos. Não existe cópia das Vendas no domínio Funding. O valor-base da
composição é `released_amount`, pois representa a saída efetivamente liberada;
quando ele não estiver disponível, a API retorna
`BASE_AMOUNT_UNAVAILABLE` em vez de inferir outro campo.

As fontes são `INVESTOR_CONTRIBUTION` (relação exclusiva com um aporte real) e
`REMO_CAPITAL` (fonte própria, sem investidor ou aporte). A fonte REMO começa
com saldo zero e só recebe saldo por lançamento administrativo explícito e
auditado. O saldo oficial, atual ou em uma data, é sempre a soma Decimal dos
eventos do ledger por `effective_date`; `created_at` registra apenas quando o
evento foi informado. Eventos na mesma data têm ordem determinística pelo ID
monotônico do ledger.

O ledger é append-only: um gatilho PostgreSQL rejeita `UPDATE` e `DELETE`, e
correções de alocações geram uma entrada `REVERSAL` ligada ao evento original.
Alocação e débito são gravados na mesma transação. Antes de um débito, a fonte
é bloqueada com `SELECT ... FOR UPDATE`, e a linha do tempo a partir da data
efetiva é recalculada para impedir tanto gasto concorrente quanto saldo futuro
negativo causado por lançamento retroativo.

O valor monetário alocado é a fonte da verdade da composição N:N. Percentuais
são derivados com `Decimal` e `ROUND_HALF_UP`. A soma pode permanecer
incompleta sem bloquear a Venda; excesso é exposto como `OVERFUNDED`, sem corte
ou normalização silenciosa. Esta fase não faz rateio de Receita nem cria
retornos automáticos de principal.

### Rateio real da Receita (Fase 2C)

Cada rateio referencia diretamente `operational_installments.id`; linhas com a
mesma combinação contrato/parcela continuam independentes. A Venda relacionada
é `contract:<operational_contract.id>`. Receitas sem esse vínculo relacional
permanecem divergentes; códigos exibidos não são usados como chave alternativa.

São rateados somente `principal_component`, `interest_component` e
`discount_amount`, campos normalizados existentes em `operational_installments`.
`paid_amount` não é usado como componente, e IOF/prejuízo não são inferidos. A
data efetiva do `PRINCIPAL_RETURN` é `payment_date`; sem data real, o rateio é
bloqueado.

A participação continua sendo `allocation.amount / released_amount`. Para cada
componente, os valores são convertidos em centavos, calcula-se com
`Decimal/ROUND_HALF_UP` o total destinado às fontes e distribui-se o resíduo
pelo método do maior resto, com desempate pelo UUID estável da allocation. Em
Funding incompleto, o gap é preservado separadamente; Funding `OVERFUNDED` é
bloqueado sem normalização.

Distribuições e itens são snapshots imutáveis da composição usada. Uma Receita
tem no máximo uma distribuição ativa, o processamento bloqueia a linha
operacional com `SELECT ... FOR UPDATE`, e distribuição, itens e retornos de
principal são confirmados em uma única transação. Correções usam reversões no
ledger append-only e uma nova versão explícita. A migration não processa nem
faz backfill das 12.120 Receitas.

## Limites preservados

- nenhuma nova sincronização está autorizada depois do batch 2;
- a migration da Fase 1C está somente preparada, sem aplicação ou promoção;
- não há autenticação nem integração bancária automática;
- dados, documentos, contas e contratos são fictícios;
- páginas consomem somente o serviço/repositório do domínio, sem acessar
  diretamente o estado financeiro no `localStorage`.

## Execução e qualidade

No Prompt de Comando do Windows:

```cmd
cd frontend
npm install
npm run lint
npm run build
npm test
cd ..
backend\.venv\Scripts\python.exe -m ruff check backend
backend\.venv\Scripts\python.exe -m pytest backend
```

Investidores, Aportes e Vendas consomem exclusivamente APIs reais, sem fallback
para mocks ou `localStorage`. Nenhuma nova sincronização ou promoção operacional
foi executada na Fase 2B.
# Autenticação da aplicação

A aplicação exige sessão por cookie `HttpOnly`. O primeiro ADMIN não é criado
por migration: use o comando idempotente `python -m app.cli bootstrap-admin`
com `FUNDING_BOOTSTRAP_ADMIN_NAME`, `FUNDING_BOOTSTRAP_ADMIN_EMAIL` e
`FUNDING_BOOTSTRAP_ADMIN_PASSWORD` configurados no ambiente. Consulte
`FASE_2F_AUTENTICACAO_CONTROLE_ACESSO.md` para a estratégia completa e os
comandos compatíveis com CMD.

## OneDrive Personal como fonte operacional

A Fase 2G adiciona `OneDriveSource` sem substituir o parser ou as quatro abas
autorizadas. A origem é selecionada por `OPERATIONAL_SOURCE=local|onedrive` e
ambas entregam uma cópia temporária ao mesmo pipeline. A conexão, verificação,
sincronização e desconexão são manuais e exclusivas de ADMIN; sincronizar cria
um batch, mas nunca promove a camada operacional automaticamente.

Consulte `FASE_2G_ONEDRIVE_PERSONAL.md` para registrar o aplicativo Microsoft,
configurar o redirect URI, gerar a chave de criptografia e operar a integração.
