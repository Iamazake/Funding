# Remo Funding — Fase 0

Fundação do sistema Remo Funding:

- Python 3.12 + FastAPI;
- SQLAlchemy 2 assíncrono + asyncpg;
- Alembic conectado ao PostgreSQL gerenciado no Supabase;
- React 18 + TypeScript + Vite;
- Tailwind CSS + fundação shadcn/ui;
- `GET /health` verificando API e banco remoto.

Não há funcionalidades de Excel, sincronização, funding, investidores,
dashboards ou autenticação nesta fase.

## Pré-requisitos

```cmd
py -3.12 --version
node --version
npm --version
```

O arquivo `.env` deve existir na raiz com `DATABASE_URL`. Nunca envie ou
adicione esse arquivo ao Git.

## Instalação do backend

Na raiz do repositório:

```cmd
py -3.12 -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install --upgrade pip
backend\.venv\Scripts\python.exe -m pip install -e "backend[dev]"
```

## Migration

```cmd
cd backend
.venv\Scripts\alembic.exe upgrade head
.venv\Scripts\alembic.exe current
cd ..
```

## Testes e qualidade do backend

```cmd
backend\.venv\Scripts\python.exe -m ruff check backend
backend\.venv\Scripts\python.exe -m pytest backend
```

## Executar a API

No primeiro CMD:

```cmd
backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload
```

Validar em outro CMD:

```cmd
curl http://127.0.0.1:8000/health
```

Resposta esperada:

```json
{"status":"ok","api":"ok","database":"connected"}
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

## Instalação e execução do frontend

```cmd
cd frontend
npm install
npm run lint
npm run build
npm run dev
```

Abra:

```text
http://127.0.0.1:5173
```

O frontend usa apenas a API FastAPI. Ele não recebe nem acessa a connection
string do PostgreSQL.

