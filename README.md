# Remo Funding — Protótipo visual funcional

Fundação validada e experiência administrativa do funding construída com
dados exclusivamente fictícios.

## Estado atual

- backend da Fase 0 preservado: Python 3.12, FastAPI, SQLAlchemy 2, asyncpg,
  Alembic e `GET /health` conectado ao PostgreSQL Supabase;
- frontend em React 18, TypeScript, Vite, Tailwind, componentes no padrão
  shadcn/ui, Lucide e Recharts;
- shell responsivo com menu recolhível, busca visual, breadcrumbs e temas
  escuro/claro;
- providers mockados substituíveis por uma futura API FastAPI;
- valores financeiros mockados armazenados como strings decimais e calculados
  em centavos inteiros quando há interação;
- nenhuma leitura de Excel, sincronização ou gravação no Supabase.

Todas as telas exibem a identificação **Ambiente demonstrativo**.

## Rotas

```text
/dashboard
/investidores
/investidores/:id
/aportes
/aportes/:id
/rateio
/contratos
/tesouraria
/relatorios
/sincronizacao
/configuracoes
```

O rateio altera somente a memória da sessão do navegador. Recarregar a página
restaura os dados demonstrativos originais.

## Fontes oficiais preservadas

1. **Cadastro de Clientes:** futura fonte operacional de clientes, contratos,
   empréstimos e amortizações. A integração está adiada.
2. **PostgreSQL Supabase:** fonte dos dados próprios do novo funding quando a
   persistência dessas funcionalidades for autorizada.
3. **Funding Remo.xlsm:** somente referência do modelo legado e reconciliação;
   nunca deve ser importado ou sincronizado.

## Pré-requisitos

Comandos para o Prompt de Comando do Windows:

```cmd
py -3.12 --version
node --version
npm --version
```

O `.env` local contém `DATABASE_URL` apenas para o backend. Nunca adicione esse
arquivo ao Git. O frontend não recebe essa variável.

## Instalação

Backend, na raiz do repositório:

```cmd
py -3.12 -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install --upgrade pip
backend\.venv\Scripts\python.exe -m pip install -e "backend[dev]"
```

Frontend:

```cmd
cd frontend
npm install
cd ..
```

## Executar localmente

Abra um CMD na raiz e inicie o backend:

```cmd
backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload
```

Em outro CMD:

```cmd
cd frontend
npm run dev
```

Abra `http://127.0.0.1:5173`. A API fica em
`http://127.0.0.1:8000` e a documentação em
`http://127.0.0.1:8000/docs`.

## Qualidade

Na raiz do repositório:

```cmd
cd frontend
npm run lint
npm run build
cd ..
backend\.venv\Scripts\python.exe -m ruff check backend
backend\.venv\Scripts\python.exe -m pytest backend
```

Para validar manualmente a saúde da API:

```cmd
curl http://127.0.0.1:8000/health
```

Resposta esperada:

```json
{"status":"ok","api":"ok","database":"connected"}
```

## Limites desta etapa

- não implementar `FileSource` ou `SharePointSource`;
- não abrir, copiar ou importar o Cadastro de Clientes;
- não criar tabelas-espelho ou migrations operacionais;
- não acessar dados reais ou abas sensíveis;
- não persistir investidores, aportes, alocações ou tesouraria;
- não implementar remuneração, PJR ou arredondamento definitivos;
- não iniciar a Fase 1B sem nova autorização.
