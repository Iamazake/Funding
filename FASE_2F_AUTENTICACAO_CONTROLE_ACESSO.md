# Fase 2F — Autenticação e controle de acesso

## Estratégia de autenticação

O Funding usa e-mail e senha com hash **Argon2id**. A API cria um token opaco
aleatório, grava somente seu hash SHA-256 em `app_auth_sessions` e entrega o
token ao navegador em cookie `HttpOnly`, `SameSite=Lax`, com duração padrão de
8 horas. O cookie é `Secure` por padrão fora de desenvolvimento/teste.

Cada requisição privada resolve a sessão no PostgreSQL e revalida sua
expiração, revogação e o status atual do usuário. Logout, redefinição de senha e
desativação revogam sessões no servidor. Nenhum token é salvo em `localStorage`.

O CORS permite credenciais somente para origins explícitas. Em desenvolvimento,
`http://localhost:5173` e `http://127.0.0.1:5173` permanecem autorizadas. Em
produção, configure `CORS_ALLOWED_ORIGINS` com a URL HTTPS real.

O ambiente local padrão usa `http://localhost:5173` no frontend e
`http://localhost:8000` na API. Não misture `localhost` e `127.0.0.1`: são
sites diferentes para a política `SameSite` do navegador, e o cookie `Lax`
não acompanha um `fetch` entre esses dois hosts. Se optar por `127.0.0.1`, use
esse mesmo host nos dois serviços.

Inicialização recomendada no CMD:

```cmd
cd backend
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host localhost --port 8000
```

Em outro terminal:

```cmd
cd frontend
npm run dev -- --host localhost
```

## Usuários e permissões

`app_users` contém UUID, nome, e-mail normalizado, hash de senha, perfil,
status, último login e timestamps. E-mail possui unicidade case-insensitive no
PostgreSQL. A senha mínima tem 10 caracteres e pode ser uma frase-senha.

- `ANALYST`: acessa as operações normais de Dashboard, Investidores, Aportes,
  Vendas, Receita, Funding e Tesouraria, inclusive rateios e validação bancária.
- `ADMIN`: possui as mesmas permissões e também gerencia usuários,
  configurações e sincronização administrativa.

Todas as APIs operacionais, de Funding e Tesouraria exigem autenticação. A
autorização ADMIN é verificada no backend. Usuários são desativados, nunca
excluídos. Uma trava transacional serializa alterações de administradores e o
sistema rejeita qualquer mudança que remova o último ADMIN ativo.

## Bootstrap do primeiro ADMIN

A migration não cria usuários. Configure as três variáveis apenas no ambiente
seguro e execute o comando administrativo a partir da pasta `backend`:

```cmd
set FUNDING_BOOTSTRAP_ADMIN_NAME=Nome do administrador
set FUNDING_BOOTSTRAP_ADMIN_EMAIL=admin@dominio.com.br
set FUNDING_BOOTSTRAP_ADMIN_PASSWORD=uma frase senha segura
.venv\Scripts\python.exe -m app.cli bootstrap-admin
```

O comando é idempotente: se o e-mail já existir, não duplica, não altera o
perfil e não sobrescreve a senha. A senha nunca é impressa. Após o bootstrap,
remova as três variáveis do ambiente de execução.

## Endpoints

Públicos:

- `GET /health`
- `POST /api/auth/login`

Autenticados:

- `GET /api/auth/me`
- `POST /api/auth/logout`
- `POST /api/auth/change-password`
- todas as APIs operacionais, Funding e Tesouraria.

Exclusivos de ADMIN:

- `GET /api/admin/users`
- `POST /api/admin/users`
- `GET /api/admin/users/{id}`
- `PATCH /api/admin/users/{id}`
- `POST /api/admin/users/{id}/reset-password`

## Auditoria e atores

`app_user_audit_events` registra bootstrap, login bem-sucedido, criação e
alteração de usuário, ativação/desativação e redefinição de senha. Não registra
senha, hash ou token. `funding_audit_events` recebeu `actor_user_id`; novos
eventos e reversões usam o usuário autenticado. A validação bancária agora
preenche `validated_by` com FK para `app_users`. Registros históricos continuam
sem ator e não recebem backfill fictício.

O login possui limitação em memória de cinco falhas por combinação de IP e
hash do e-mail em uma janela móvel de 15 minutos. O bloqueio expira
automaticamente, não revela a existência do e-mail e nunca armazena a senha.

## Limites desta fase

Não há cadastro público, recuperação por e-mail, envio de e-mail, MFA, SSO ou
login social. A redefinição administrativa substitui a senha e revoga sessões;
um fluxo obrigatório de senha temporária fica para uma etapa futura.
