# Remo Funding — protótipo funcional de domínio

Protótipo React 18 + TypeScript para investidores, aportes, remuneração de
capital, contratos, composição de funding, Receita e tesouraria. Todos os registros são
fictícios e persistidos em um repositório demonstrativo versionado no
`localStorage`.

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

## Limites preservados

- nenhum Excel ou Cadastro de Clientes é lido;
- nenhuma conexão com SharePoint, Supabase ou banco é realizada;
- nenhuma migration ou entidade de backend foi criada;
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

O backend existente foi preservado. Qualquer integração com Excel, banco real
ou Supabase exige uma aprovação futura e explícita.
