# Fase 3A — Hardening e preparação para deploy/homologação

## Estado protegido

- Promotion corrente: `#2`, batch `#3`.
- Vendas: `1.528`; Receitas: `12.866`.
- Julho/2026 por `payment_date`: 184 registros, R$ 89.305,17.
- Venda `2406001474`: Funding `COMPLETE`, allocation ativa de R$ 300,00.
- Ledger: 2 eventos, saldo R$ 99.700,00.
- Validação bancária: `VALIDATED`.
- Batches: `#1`, `#2`, `#3`; sync runs: 4.

Esta fase não sincroniza, promove, recalcula ledger, recria allocations nem
gera distribuições ou retornos de principal.

## Arquitetura recomendada, sem escolha de provedor

### Opção A — um host público e dois serviços (recomendada)

```text
https://DOMINIO/         -> arquivos estáticos de frontend/dist
https://DOMINIO/api/*    -> backend FastAPI
https://DOMINIO/health   -> backend FastAPI
```

Um reverse proxy, ingress ou edge router termina TLS, serve o frontend e
encaminha `/api` e `/health`. Qualquer rota que não seja arquivo estático,
`/api/*` ou `/health` deve retornar `frontend/dist/index.html`; isso garante
refresh direto em `/dashboard`, `/vendas`, `/receita`, `/investidores`,
`/aportes`, `/tesouraria` e `/sincronizacao`.

### Opção B — frontend e API em serviços diferentes sob o mesmo domínio

É equivalente à opção A quando um gateway publica ambos no mesmo host. Mantém
cookie first-party, elimina CORS no navegador e permite escalar os serviços de
forma independente.

### Opção C — origins públicas distintas

É suportada por `VITE_API_URL` e `CORS_ALLOWED_ORIGINS`, mas exige configuração
exata de CORS, cookies e política de proxy. Deve ser usada somente se a
plataforma não suportar o roteamento das opções A/B.

Nenhum provedor de cloud foi selecionado nesta fase.

## Classificação da auditoria

### PRODUCTION_READY

- FastAPI, SQLAlchemy assíncrono e PostgreSQL/Supabase.
- Sessões opacas: só o hash fica no banco; cookie é HttpOnly e `SameSite=Lax`.
- `Secure=true` é obrigatório em produção e `Path=/` é preservado ao criar e
  remover o cookie.
- `/health` verifica API e banco, responde 503 sem detalhes internos quando o
  PostgreSQL não está disponível.
- CORS usa origins explícitas, credenciais e métodos/headers limitados; `*` é
  rejeitado.
- Endpoints de sync, promotion, batches, OneDrive e usuários exigem ADMIN.
- APIs operacionais, Funding e Tesouraria exigem sessão autenticada.
- DTOs operacionais não expõem `raw_data`, hash de linha nem CPF.
- Query string do callback OAuth é removida do access log.
- `.env`, logs, builds, caches, dados reais e venv não são versionados.
- Alembic lê a URL somente do ambiente e opera de forma transacional.

### LOCAL_ONLY

- `OPERATIONAL_EXCEL_PATH` e `OPERATIONAL_SOURCE=local` são opções locais.
- Frontend Vite e seu proxy para `localhost:8000` são apenas desenvolvimento.
- `AUTH_COOKIE_SECURE=false` é permitido somente fora de produção.
- Origins `localhost`/`127.0.0.1`, docs OpenAPI e hosts locais são adicionados
  somente fora de produção.

### REQUIRES_CHANGE antes do go-live

- Escolher provedor/região, domínio, DNS, certificado TLS e reverse proxy.
- Preencher o cofre de secrets e as variáveis públicas do ambiente.
- Cadastrar o callback HTTPS no Microsoft Entra/Azure.
- Confirmar o modo de conexão Supabase apropriado à rede do backend.
- Confirmar backup recuperável e executar um restore drill em ambiente isolado.
- Configurar HSTS, limites de request e rate limiting no edge/proxy.
- Para múltiplas réplicas do backend, substituir ou complementar o rate limiter
  de login em memória por limite compartilhado no edge/Redis. Uma réplica pode
  operar com a proteção atual mais rate limiting no edge.

## Configuração por ambiente

Produção falha ao iniciar se houver ambiente inválido, SSL não obrigatório na
URL do PostgreSQL, cookie inseguro, flag histórica de testes, frontend sem
HTTPS, host confiável ausente ou configuração OneDrive incompleta quando essa
origem estiver ativa.

Os templates são:

- `deploy/backend.production.env.example`
- `deploy/frontend.production.env.example`
- `.env.example` para desenvolvimento

Para same-origin, deixe `VITE_API_URL` vazio e `CORS_ALLOWED_ORIGINS` vazio.
Quando houver origins distintas, defina ambos explicitamente com HTTPS.

## Cookies, login e proxy

O fluxo validado é:

```text
POST /api/auth/login -> Set-Cookie HttpOnly; Secure; SameSite=Lax; Path=/
GET  /api/auth/me    -> revalida token, expiração, revogação e usuário ativo
refresh do browser   -> frontend reconstrói a sessão chamando /api/auth/me
POST /api/auth/logout -> revoga no banco e remove o cookie com os mesmos atributos
```

O proxy deve enviar `X-Forwarded-Proto=https` e o host original. Inicie Uvicorn
com `--proxy-headers` e limite `--forwarded-allow-ips` aos endereços do proxy;
não confie em `*` numa rede pública irrestrita.

## OneDrive OAuth

Cadastre exatamente estes Redirect URIs do tipo Web:

```text
http://localhost:8000/api/integrations/onedrive/callback
https://DOMINIO/api/integrations/onedrive/callback
```

Não use wildcard, query string ou barra final adicional. Mantenha o callback
local e adicione o callback público quando o domínio estiver definido.
`ONEDRIVE_REDIRECT_URI` deve ser igual ao callback do ambiente em execução.
Nenhuma alteração automática é feita no Microsoft Entra.

## Secrets

Somente o backend recebe credenciais de banco, OAuth, criptografia, bootstrap e
sessão. O frontend recebe no máximo `VITE_API_URL`, que é uma URL pública.

Injete secrets pelo secret manager da plataforma. Não os coloque em argumentos
de comando, imagens, logs ou artefatos Vite. Depois de `bootstrap-admin`, remova
as três variáveis de bootstrap do runtime.

## Banco, pool e migrations

O banco permanece PostgreSQL no Supabase. Para backend persistente, prefira a
conexão direta quando a rede suportar IPv6; em rede IPv4 sem add-on, use o
Supavisor em session mode. Transaction mode é voltado a runtimes serverless e
não suporta prepared statements sem ajuste adicional. Runtime e migration
podem usar URLs separadas no secret manager, mas Alembic deve receber uma URL
direta/session adequada e com SSL obrigatório.

Procedimento de release, executado uma vez antes de iniciar réplicas:

```cmd
cd backend
.venv\Scripts\alembic.exe current
.venv\Scripts\alembic.exe heads
.venv\Scripts\alembic.exe upgrade head
.venv\Scripts\alembic.exe check
```

Exija um único head, backup confirmado e nenhuma operação inesperada no
`alembic check`. Não execute migrations concorrentes no startup de cada réplica.

## Backup e restauração

Antes do go-live e de cada migration material:

1. No Supabase Dashboard, abra Database > Backups e confirme um restore point
   anterior ao deploy. Registre horário UTC, retenção e responsável.
2. Em planos sem backup diário/PITR adequado, ou como cópia adicional, gere um
   dump lógico pela Supabase CLI/`pg_dump` usando conexão direta de gestão.
3. Criptografe o dump, gere checksum e armazene-o fora do projeto/conta de
   produção, com acesso mínimo e política de retenção.
4. Faça restore drill primeiro em novo projeto/ambiente isolado; valide schema,
   migrations, contagens, ledger e autenticação.
5. Restore em produção exige incidente aprovado, janela de indisponibilidade e
   definição explícita do ponto no tempo. Nunca faça limpeza preventiva.

Backups físicos/PITR podem não gerar arquivo lógico baixável; nesse caso use
Supabase CLI ou `pg_dump` para a cópia externa. A restauração gerenciada deixa o
projeto indisponível durante o processo.

Tabelas críticas incluem `funding_*`, `treasury_*`, `app_users`,
`app_auth_sessions`, `app_user_audit_events`, `operational_*`, `excel_*`,
`sync_runs`, `operational_import_batches` e `operational_source_connections`.
O backup deve ser do banco inteiro para preservar FKs e auditoria.

Referências oficiais:

- https://supabase.com/docs/guides/platform/backups
- https://supabase.com/docs/guides/database/connecting-to-postgres
- https://supabase.com/docs/guides/troubleshooting/download-logical-backups

## Build e start

Frontend:

```cmd
cd frontend
npm ci
npm test
npm run lint
npm run build
```

Publique somente `frontend/dist`. Configure o fallback SPA no host estático.

Backend:

```cmd
cd backend
.venv\Scripts\python.exe -m pip install .
.venv\Scripts\alembic.exe upgrade head
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers
```

Na plataforma, substitua a porta pelo valor fornecido e configure
`forwarded-allow-ips` para o proxy real.

## Checklist de go-live

- [ ] Provedor, região, domínio e janela de homologação aprovados.
- [ ] TLS válido; redirect HTTP->HTTPS; HSTS no edge após validar HTTPS.
- [ ] `/api/*` e `/health` encaminhados; fallback SPA testado por refresh.
- [ ] Variáveis/secrets configurados; nenhum secret presente no frontend.
- [ ] `APP_ENV=production`, cookie seguro, docs desabilitadas e flag histórica falsa.
- [ ] CORS vazio em same-origin ou lista HTTPS explícita sem wildcard.
- [ ] Callback local e público cadastrados no Entra; OAuth testado por ADMIN.
- [ ] Backup/restore point e restore drill confirmados.
- [ ] Alembic com um head, `upgrade head` e `check` concluídos.
- [ ] Health, login/me/refresh/logout e perfis ADMIN/ANALYST testados.
- [ ] Sync e promotion confirmados como exclusivos de ADMIN.
- [ ] Smoke de Vendas, Receita, Funding e Tesouraria concluído.
- [ ] Invariantes financeiros comparados antes/depois do deploy.
- [ ] Observabilidade e alertas de health/5xx configurados sem payload sensível.
- [ ] Rollback de aplicação documentado; restore de banco reservado a incidente.

## Limitação conhecida

O batch #3 foi criado antes do armazenamento de `NOME_CLIENTE` de
`ECON_EMPRESTIMOS`; muitos nomes seguem ausentes. Isso é apresentação, não
bloqueia deploy. Uma sincronização futura explicitamente autorizada criará novo
batch e preview. Nenhuma sincronização faz parte desta fase.
