# Sistema de Funding — Remo

Plano do projeto consolidado com as alterações de infraestrutura autorizadas
em 24/07/2026 e a correção de fontes de dados autorizada em 30/07/2026. Todas
as demais decisões do plano original permanecem válidas.

---

## 1. Visão geral

A Remo é uma financeira de empréstimo pessoal. A operação de crédito
(clientes, contratos, empréstimos, parcelas e pagamentos) roda e continuará
rodando no arquivo Excel operacional **Cadastro de Clientes**, atualmente
disponível em uma pasta local sincronizada pelo OneDrive. Esse arquivo é a
fonte da verdade dos dados operacionais existentes.

O arquivo **Funding Remo.xlsm** é exclusivamente um modelo legado de
referência funcional e reconciliação. Ele não é fonte operacional, não será
importado e não será sincronizado com o PostgreSQL.

O sistema novo é responsável por:

1. **Ler e espelhar** os dados operacionais do arquivo Cadastro de Clientes em
   um banco de dados limpo e normalizado (fluxo de mão única, somente leitura —
   o sistema nunca escreve no Excel).
2. **Gerir o funding**: investidores, aportes, rateio do capital entre
   contratos (sem o limite atual de 4 partes), remuneração mensal, PJR,
   reinvestimento e tesouraria.
3. **Entregar visual de alto nível**: dashboards, gráficos e KPIs de safra,
   receita, inadimplência, PDD e retorno por investidor.

A conexão automática com o SharePoint/OneDrive (Microsoft Graph) fica para uma
fase posterior. Na fase inicial, o sistema lê uma cópia local do Cadastro de
Clientes a partir do caminho configurado em `OPERATIONAL_EXCEL_PATH`, mas a
origem do arquivo é uma peça trocável da arquitetura.

### Divisão oficial das fontes

1. **Cadastro de Clientes (Excel operacional):** fonte da verdade para
   clientes, contratos, empréstimos, amortizações e demais dados operacionais
   existentes. É a única planilha que o `FileSource` poderá importar e
   sincronizar.
2. **PostgreSQL Supabase:** fonte da verdade para os dados próprios do novo
   sistema de funding, incluindo investidores canônicos, aportes, alocações,
   remunerações, PJR, reinvestimentos e movimentos de tesouraria.
3. **Funding Remo.xlsm:** referência funcional do modelo legado, fórmulas e
   reconciliação. Nunca importar, espelhar ou sincronizar.

---

## 2. Stack tecnológica

| Camada | Tecnologia | Por quê |
|---|---|---|
| Backend / API | **Python 3.12 + FastAPI** | Ecossistema para leitura de Excel, limpeza, cálculo financeiro e documentação automática da API. |
| Validação de dados | **Pydantic** | Garante que dados de entrada estejam no formato correto. |
| Banco de dados | **PostgreSQL gerenciado no Supabase** | PostgreSQL robusto sem dependência de virtualização ou banco local. Valores monetários sempre em `NUMERIC(14,2)`. |
| ORM / Migrations | **SQLAlchemy 2 assíncrono + asyncpg + Alembic** | Modelagem em código, acesso assíncrono e histórico versionado de mudanças. |
| Frontend | **React 18 + TypeScript + Vite** | Stack de dashboards com tipagem estática. |
| Estilo / UI | **Tailwind CSS + shadcn/ui** | Visual profissional, consistente e reutilizável. |
| Gráficos | **Recharts** | Gráficos interativos integrados ao React. |
| Leitura do Excel | **pandas + openpyxl** | Leitura de `.xlsm` com valores calculados em cache. |
| Agendamento de sync | **APScheduler** (fase local) → **webhooks Microsoft Graph** (fase SharePoint) | Sincronização periódica agora e por evento posteriormente. |
| Autenticação | **JWT + bcrypt** (fase de segurança) | Login com perfis de acesso. |

### Infraestrutura autorizada

- O banco continua sendo PostgreSQL.
- O PostgreSQL da aplicação é gerenciado no Supabase.
- Docker, Docker Desktop, Docker Compose, WSL, virtualização, PostgreSQL local
  e `psql` local não são requisitos obrigatórios.
- O backend FastAPI é o único componente que acessa o PostgreSQL.
- O frontend nunca recebe nem utiliza a connection string.
- A URL do banco existe exclusivamente na variável de ambiente `DATABASE_URL`.
- Senhas, connection strings, service role keys e demais credenciais nunca
  entram no código, frontend ou Git.
- Alembic executa migrations diretamente no PostgreSQL do Supabase.

---

## 3. Arquitetura

```text
┌────────────────────┐
│ Cadastro de        │  ← fonte da verdade operacional
│ Clientes (Excel)   │     caminho em OPERATIONAL_EXCEL_PATH
└─────────┬──────────┘
          │  somente leitura
          ▼
┌────────────────────┐
│  CONECTOR (Python) │  FileSource (trocável):
│  - copia o arquivo │   • LocalFileSource  (fase 1)
│  - lê as abas      │   • SharePointSource (depois, via Graph)
│  - valida e limpa  │
└─────────┬──────────┘
          ▼
┌────────────────────┐
│ PostgreSQL         │  Supabase gerenciado:
│ (somente backend)  │  espelho operacional + funding próprio
└─────────┬──────────┘
          ▼
┌────────────────────┐
│  API (FastAPI)     │  SQLAlchemy 2 + asyncpg
│                    │  endpoints REST
└─────────┬──────────┘
          ▼
┌────────────────────┐
│  Frontend (React)  │  nunca acessa o PostgreSQL diretamente
└────────────────────┘

┌────────────────────┐
│ Funding Remo.xlsm  │  referência legada e reconciliação
│ NÃO sincronizar    │  sem fluxo de importação para o banco
└────────────────────┘
```

### Regras de ouro

- **Excel operacional é intocável.** O sistema nunca escreve no Cadastro de
  Clientes. Sempre copiar o arquivo antes de ler.
- **O legado não é fonte.** `Funding Remo.xlsm` nunca é importado, espelhado ou
  sincronizado; seu diagnóstico serve apenas de referência funcional.
- **Origem do arquivo é plugável.** Todo o código conversa com uma interface
  `FileSource`; trocar de pasta local para SharePoint não altera nada além do
  conector.
- **Dinheiro é `Decimal`/`NUMERIC`.** Nunca float, em nenhuma camada. Colunas
  monetárias usam `NUMERIC(14,2)`.
- **Toda sincronização é registrada** com data/hora, linhas lidas e erros.
- **Dado sujo não derruba o sistema.** Linhas problemáticas vão para uma fila
  de inconsistências e o restante segue.
- **Credenciais ficam fora do código.** O banco é configurado exclusivamente
  por `DATABASE_URL` no `.env` local ou no ambiente seguro de implantação.
- **Caminho operacional fica fora do código.** O caminho real do Cadastro de
  Clientes existe exclusivamente em `OPERATIONAL_EXCEL_PATH` no `.env` local
  ou no ambiente seguro de implantação.

---

## 4. Estrutura do repositório

```text
funding/
├── PLANO_SISTEMA_FUNDING_REMO.md
├── CLAUDE.md
├── README.md
├── DIAGNOSTICO_MODELO_LEGADO_FUNDING.md
├── FASE_1A_DIAGNOSTICO_CADASTRO_CLIENTES.md
├── .env.example
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── api/
│   │   └── services/
│   │       ├── excel/
│   │       ├── funding/
│   │       └── kpi/
│   ├── tests/
│   ├── alembic/
│   ├── alembic.ini
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   │   ├── charts/
│   │   │   └── kpi/
│   │   ├── lib/
│   │   └── styles/
│   └── package.json
└── data/
    └── input/
```

Um `docker-compose.yml` pode ser adicionado no futuro exclusivamente como
alternativa opcional de desenvolvimento local. Ele não faz parte dos
pré-requisitos nem bloqueia qualquer fase.

---

## 5. Modelo de dados (núcleo)

### Espelho do Cadastro de Clientes (recarregado a cada sync)

- **clientes** — cod_cliente, cpf normalizado e único, nome canônico,
  data_nasc, rating.
- **contratos** — cod_contrato, cliente_id, datas, prazo, principal, pmt, iof,
  taxa_juros, taxa_cet, tir, status, tipo e mês_operação.
- **parcelas** — contrato_id, número, vencimento, valor, valor_pago,
  dt_pagamento, status, atraso_dias, principal, juros, iof e prejuízo.
- **inconsistencias** — linha original, aba, motivo e status de revisão.

### Dados próprios do sistema

- **investidores** — nome, código, tipo, contato, risco, dados bancários
  criptografados e dia de pagamento.
- **aportes** — investidor_id, valor, datas, taxa_remuneração e status.
- **funding_rateio** — aporte_id ↔ contrato_id e valor alocado.
- **movimentos_tesouraria** — investidor_id, tipo, valor, data e referência.
- **parametros** — matriz de rating, faixas de atraso, PDD, tiers de PJR e
  taxas padrão.
- **sync_log** — registro de cada sincronização.

As tabelas deste modelo são implementadas somente nas fases correspondentes.
Os dados próprios de funding nunca são recarregados a partir de
`Funding Remo.xlsm`.

---

## 6. Fases do projeto

### Fase 0 — Fundação

- Validar Node.js, npm e Python 3.12.
- Criar repositório Git e estrutura da seção 4.
- Criar o projeto PostgreSQL gerenciado no Supabase.
- Configurar `DATABASE_URL` exclusivamente no `.env` local.
- Configurar SQLAlchemy 2 assíncrono com `asyncpg`.
- Configurar Alembic para o banco remoto e executar a migration inicial.
- Criar o esqueleto FastAPI.
- Criar `GET /health`, confirmando que a API está viva e que o PostgreSQL do
  Supabase responde.
- Criar o esqueleto React 18 + TypeScript + Vite + Tailwind/shadcn.
- Validar backend, frontend, testes e conexão remota.

**Limite:** não implementar Excel, sincronização, investidores, aportes,
rateio, remuneração, tesouraria, dashboards ou autenticação.

**Entrega:** fundação completa rodando sem dependência obrigatória de Docker,
WSL, virtualização, PostgreSQL ou `psql` local.

### Fase 1A — Diagnóstico do Cadastro de Clientes

- Exigir `OPERATIONAL_EXCEL_PATH` configurado exclusivamente no `.env` local.
- Confirmar que o arquivo está disponível localmente sem exibir o caminho real
  ou qualquer conteúdo sensível.
- Copiar o arquivo para uma área temporária única e analisar somente a cópia.
- Identificar arquivo, hash, abas, cabeçalhos, colunas, tipos, fórmulas,
  chaves, relacionamentos, inconsistências e diferenças em relação ao plano.
- Analisar especialmente `BCLI_CADASTRO`, `DFEN_CONTRATO`,
  `ECON_EMPRESTIMOS`, `ECON_AMORTIZACOES` e demais abas operacionais.
- Entregar `FASE_1A_DIAGNOSTICO_CADASTRO_CLIENTES.md`.

**Limite:** não acessar o Supabase, criar migrations nem implementar
`FileSource`, reader, cleaner ou sincronização definitiva.

**Status:** concluída e aprovada. O relatório técnico permanece em
`FASE_1A_DIAGNOSTICO_CADASTRO_CLIENTES.md`.

### Etapa intermediária — Protótipo visual funcional do funding

Por alteração autorizada na ordem do projeto, esta etapa ocorre depois da
Fase 1A e antes da Fase 1B. A integração operacional fica adiada.

- Construir a experiência visual completa com React 18, TypeScript, Vite,
  Tailwind, componentes shadcn/ui e Recharts.
- Usar exclusivamente dados fictícios, controlados e identificados como
  demonstrativos.
- Criar providers substituíveis para dashboard, investidores, aportes,
  alocações, tesouraria e contratos operacionais.
- Implementar inicialmente somente providers mockados; as páginas não acessam
  os mocks diretamente.
- Criar shell administrativo responsivo, tema escuro padrão e tema claro.
- Criar as rotas de dashboard, investidores, aportes, rateio, contratos,
  tesouraria, relatórios, sincronização e configurações.
- Permitir simulações apenas no estado local da sessão.
- Preservar dinheiro como strings decimais ou centavos inteiros; não usar
  `float` em regras financeiras.

**Limite:** não ler ou copiar Excel, implementar `FileSource`, sincronizar,
criar tabelas-espelho, criar migrations operacionais, usar dados pessoais reais,
gravar no Supabase ou implementar cálculos financeiros definitivos.

**Fontes preservadas:** Cadastro de Clientes continua sendo a futura fonte
operacional; Supabase continua sendo a fonte futura dos dados próprios do
funding; `Funding Remo.xlsm` continua somente como referência legada.

### Fase 1B — Conector Excel + espelho

- Implementação preparatória e migration estrutural concluídas em 07/08/2026,
  após nova autorização expressa.
- A primeira sincronização real foi executada uma única vez como teste de
  ingestão. A reconciliação 1B.1 foi concluída e as regras 1B.2 foram preparadas
  sem reclassificar o batch 1.
- Qualquer nova sincronização permanece bloqueada até autorização específica.
- Implementar `FileSource` e `LocalFileSource` lendo uma cópia do arquivo
  indicado por `OPERATIONAL_EXCEL_PATH`.
- Ler somente as abas operacionais comprovadas no novo diagnóstico.
- Normalizar CPF, nomes e datas; enviar valores inválidos e `#VALUE!` para a
  fila de inconsistências.
- Sincronizar manualmente e registrar em `sync_log`.
- Nunca ler, importar ou sincronizar `Funding Remo.xlsm`.

### Fase 1C — camada operacional normalizada

- Materializar snapshots normalizados a partir de um batch sucedido e
  explicitamente informado.
- Preservar os espelhos `excel_*` e todos os snapshots anteriores.
- Manter DFEN_CONTRATO como fonte primária do contrato e ECON_EMPRESTIMOS como
  entidade complementar rastreável, inclusive para órfãos.
- Preservar cada linha de amortização sem impor unicidade de contrato + parcela.
- Preparar parcela 1:N movimentos sem inventar regra de pagamento parcial.
- Referenciar inconsistências existentes em vez de duplicá-las.
- Manter o frontend mockado até a fase de API autorizada.

**Status:** migration aplicada e batch 2 promovido como promoção 1. A API real
expõe Vendas e Receita com paginação, filtros, contadores e DTOs seguros. As
telas principais consomem esses endpoints sem fallback para dados fictícios.

### Fase 2 — API + primeiras telas

- Endpoints de clientes, contratos, parcelas e carteira.
- Telas de consulta, detalhe do contrato e sincronização.

### Fase 3 — Módulo de funding

- CRUD de investidores e aportes.
- Rateio N:N, remuneração, PJR, reinvestimento e tesouraria.

### Fase 4 — Dashboards e KPIs

- Dashboard geral, safra, receita, inadimplência, PDD, funding e painel do
  investidor.

### Fase 5 — Segurança e LGPD

- Login, perfis, criptografia de dados sensíveis, auditoria e backups.

### Fase 6 — Conexão SharePoint

- `SharePointSource` via Microsoft Graph, webhooks e verificação periódica.

---

## 7. Padrões visuais

- Tema escuro e claro, com escuro como padrão.
- Paleta sóbria de fintech; verde e vermelho reservados para resultados.
- Cards de KPI no topo, gráficos abaixo e tabelas por último.
- Valores monetários em R$ e datas em `dd/mm/aaaa`.
- Gráficos exportáveis como imagem nas fases correspondentes.

---

## 8. Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Equipe altera o layout do Cadastro de Clientes | Validar layout e alertar sem falhar silenciosamente. |
| Arquivo operacional aberto durante leitura | Copiar antes de ler. |
| Fórmulas com cache desatualizado | Exibir data/hora do arquivo lido. |
| Dados sujos | Fila de inconsistências. |
| Erro de centavos | `Decimal`/`NUMERIC(14,2)` e testes. |
| Credencial do Supabase exposta | `.env` ignorado pelo Git, `.env.example` sem segredo e backend como único consumidor. |
| Caminho do arquivo exposto ou fixo | `OPERATIONAL_EXCEL_PATH` somente no `.env` local; nunca registrar o valor real em logs ou Git. |
| Legado importado por engano | Bloquear `Funding Remo.xlsm` como fonte e manter seu uso somente para reconciliação. |
| Banco remoto indisponível | `/health` retorna estado da API e do banco sem expor detalhes internos. |
| Rede sem IPv6 | Usar Session pooler do Supabase em porta 5432. |

---

## 9. Comandos iniciais da Fase 0 no CMD

Os comandos oficiais e atualizados estão no `README.md`. Nenhum comando da
Fase 0 depende de Docker, WSL, PostgreSQL local ou sintaxe exclusiva de
PowerShell.
