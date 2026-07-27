# Sistema de Funding — Remo

Plano do projeto consolidado com a alteração de infraestrutura autorizada em
24/07/2026. Todas as decisões do plano original permanecem válidas, exceto a
obrigatoriedade de Docker, WSL e PostgreSQL local na Fase 0.

---

## 1. Visão geral

A Remo é uma financeira de empréstimo pessoal. A operação de crédito
(clientes, contratos, parcelas, pagamentos) roda e continuará rodando em
**Excel** (`Funding_Remo.xlsm`), que é a fonte da verdade. O sistema novo é uma
camada por cima do Excel, responsável por:

1. **Ler e espelhar** os dados do Excel em um banco de dados limpo e
   normalizado (fluxo de mão única, somente leitura — o sistema nunca escreve
   no Excel).
2. **Gerir o funding**: investidores, aportes, rateio do capital entre
   contratos (sem o limite atual de 4 partes), remuneração mensal, PJR,
   reinvestimento e tesouraria.
3. **Entregar visual de alto nível**: dashboards, gráficos e KPIs de safra,
   receita, inadimplência, PDD e retorno por investidor.

A conexão automática com o SharePoint/OneDrive (Microsoft Graph) fica para uma
fase posterior. Na fase inicial, o sistema lê uma cópia local do arquivo, mas a
origem do arquivo é uma peça trocável da arquitetura.

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
│  Excel (.xlsm)     │  ← fonte da verdade (operado pela equipe)
│  Funding_Remo      │
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
│ PostgreSQL         │  Supabase gerenciado
│ (somente backend)  │  espelho normalizado + funding
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
```

### Regras de ouro

- **Excel é intocável.** O sistema nunca escreve nele. Sempre copiar o arquivo
  antes de ler.
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

---

## 4. Estrutura do repositório

```text
funding/
├── PLANO_SISTEMA_FUNDING_REMO.md
├── CLAUDE.md
├── README.md
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

### Espelho do Excel (recarregado a cada sync)

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

### Fase 1 — Conector Excel + espelho

- Implementar `FileSource` e `LocalFileSource` lendo uma cópia em
  `data/input/`.
- Ler as abas previstas no plano original.
- Normalizar CPF, nomes e datas; enviar valores inválidos e `#VALUE!` para a
  fila de inconsistências.
- Sincronizar manualmente e registrar em `sync_log`.

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
| Equipe altera o layout do Excel | Validar layout e alertar sem falhar silenciosamente. |
| Arquivo aberto durante leitura | Copiar antes de ler. |
| Fórmulas com cache desatualizado | Exibir data/hora do arquivo lido. |
| Dados sujos | Fila de inconsistências. |
| Erro de centavos | `Decimal`/`NUMERIC(14,2)` e testes. |
| Credencial do Supabase exposta | `.env` ignorado pelo Git, `.env.example` sem segredo e backend como único consumidor. |
| Banco remoto indisponível | `/health` retorna estado da API e do banco sem expor detalhes internos. |
| Rede sem IPv6 | Usar Session pooler do Supabase em porta 5432. |

---

## 9. Comandos iniciais da Fase 0 no CMD

Os comandos oficiais e atualizados estão no `README.md`. Nenhum comando da
Fase 0 depende de Docker, WSL, PostgreSQL local ou sintaxe exclusiva de
PowerShell.

