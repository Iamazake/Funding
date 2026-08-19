# Fase 2G — OneDrive Personal como fonte operacional

## Arquitetura e limites

`LocalFileSource` e `OneDriveSource` implementam a mesma interface `FileSource`.
Cada origem produz um `StagedFile` local, isolado e com SHA-256; a partir daí,
reader, allowlist, mapper, validação, warnings, divergências e criação de batch
são exatamente os componentes existentes. O arquivo temporário é removido ao
sair do contexto, inclusive quando o parser falha.

Esta fase é exclusivamente manual. Não há webhook, scheduler, polling, delta
sync ou promoção automática. O botão **Sincronizar** cria/reutiliza o fluxo de
batch já existente; a promoção continua separada e explícita.

## Registrar o aplicativo Microsoft

1. No Microsoft Entra, crie um App registration.
2. Em **Supported account types**, selecione contas Microsoft pessoais.
3. Adicione uma plataforma **Web** e registre o redirect URI exato.
4. Em **API permissions**, adicione a permissão delegada Microsoft Graph
   `Files.Read`. Não conceda `Files.ReadWrite`.
5. Crie um client secret e armazene-o apenas no secret manager/ambiente do
   backend.

Em `ONEDRIVE_CLIENT_SECRET`, copie o campo **Value** exibido ao criar o secret.
O **Secret ID** é apenas um identificador UUID e não autentica o aplicativo; o
backend rejeita esse formato antes de iniciar o OAuth.

O backend usa Authorization Code Flow confidencial por MSAL, autoridade
`https://login.microsoftonline.com/consumers` e escopo explícito `Files.Read`.
O MSAL inclui os escopos OIDC reservados e `offline_access` necessários ao fluxo
e mantém a renovação silenciosa no token cache. O login Microsoft não substitui
a sessão ADMIN/ANALYST do Funding.

O fluxo solicita `response_mode=form_post`. Portanto, o Microsoft Entra envia
`code` e `state` no corpo `application/x-www-form-urlencoded` de um `POST`, e
não na query string do callback. O callback não depende do cookie Funding
nesse POST cross-site: o `state` descartável localiza o ADMIN que iniciou o
fluxo, e o backend confirma novamente que ele continua ativo e com papel
`ADMIN` antes da troca do código.

Em desenvolvimento, o redirect registrado pode ser:

```text
http://localhost:8000/api/integrations/onedrive/callback
```

Em produção, registre exatamente:

```text
https://<HOST_PUBLICO>/api/integrations/onedrive/callback
```

O valor no Entra e `ONEDRIVE_REDIRECT_URI` precisam ser idênticos. Não use um
hostname aleatório de Quick Tunnel como configuração permanente. O redirect
final para a UI é montado a partir de `FRONTEND_BASE_URL`.

Em desenvolvimento, configure `FRONTEND_BASE_URL=http://localhost:5173`. Assim,
o callback do FastAPI sempre termina em
`http://localhost:5173/sincronizacao`, nunca em uma rota relativa do backend.

## Variáveis de ambiente

```dotenv
OPERATIONAL_SOURCE=onedrive
ONEDRIVE_CLIENT_ID=<application-client-id>
ONEDRIVE_CLIENT_SECRET=<secret-fornecido-pelo-entra>
ONEDRIVE_REDIRECT_URI=https://<HOST_PUBLICO>/api/integrations/onedrive/callback
FRONTEND_BASE_URL=https://<HOST_PUBLICO>
ONEDRIVE_AUTHORITY=https://login.microsoftonline.com/consumers
ONEDRIVE_FILE_PATH=/01. CADASTRO DE CLIENTES/01. REMO - SOLUCOES E NEGOCIOS/Cadastro de Clientes.xlsm
ONEDRIVE_TOKEN_ENCRYPTION_KEY=<chave-fernet>
```

Gere uma chave Fernet fora do repositório e copie somente para o ambiente:

```cmd
backend\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Essa chave não deve ficar no banco, documentação, frontend ou Git. O backend
criptografa com Fernet (AES-128-CBC + HMAC-SHA256 autenticado) tanto o cache
serializado do MSAL quanto o contexto transitório do fluxo OAuth. Access token,
refresh token e cache nunca são retornados à UI.

## Operação administrativa

1. Entre no Funding como ADMIN e abra **Administração → Sincronização**.
2. Clique **Conectar OneDrive** e autorize a conta Microsoft pessoal.
3. O primeiro callback lista os filhos da raiz e navega pelas duas pastas por
   `driveItem ID`, sempre comparando cada nome de forma estritamente exata.
   Arquivos `(2)`, `1` ou `-DESKTOP` aparecem somente no diagnóstico e nunca
   são candidatos automáticos.
4. Após validar nome, extensão e metadados, o backend persiste `drive_id` e
   `drive_item_id`. Consultas posteriores usam o ID, que continua estável se o
   item for movido ou renomeado.
5. Clique **Verificar atualização**. Metadados evitam downloads desnecessários,
   mas o SHA-256 comparado com o último sync sucedido é a decisão definitiva.
6. Quando houver nova versão, clique **Sincronizar**. O Graph transmite o
   conteúdo em streaming para um arquivo temporário e o pipeline existente cria
   o batch e o relatório de qualidade.
7. Revise o batch e use o comando/processo de promoção existente somente com
   autorização explícita.

No Prompt de Comando, a promoção explícita de um batch já revisado permanece:

```cmd
backend\.venv\Scripts\python.exe -m app.cli promote-operational-batch <BATCH_ID>
```

Esse comando não faz parte da conexão ou sincronização OneDrive e nunca é
executado automaticamente.

Se a autorização expirar ou for revogada, o status muda para
`RECONNECT_REQUIRED`; não existe fallback silencioso para o arquivo local.
Nesse estado, um ADMIN usa **Reconectar OneDrive** e conclui novamente o OAuth.
**Desconectar** remove o token cache local e os identificadores ativos, mas
preserva batches, promotions, Vendas, Receita, Funding e Tesouraria.

## Alternar fontes

Para desenvolvimento local:

```dotenv
OPERATIONAL_SOURCE=local
OPERATIONAL_EXCEL_PATH=<caminho-local-configurado-fora-do-git>
```

Para produção com OneDrive, use `OPERATIONAL_SOURCE=onedrive` e configure todas
as variáveis Microsoft. Trocar a variável nunca importa, sincroniza ou promove
dados por si só; uma ação manual de ADMIN continua obrigatória.

## Segurança e auditoria

O state OAuth usa aleatoriedade criptográfica, é armazenado apenas por hash,
expira rapidamente, fica vinculado ao ADMIN e é consumido uma única vez. O
backend audita conexão, desconexão, verificação, arquivo ausente, reconexão e o
ciclo de sincronização sem incluir código, token, secret, cache ou URL de
download pré-autenticada. Como proteção adicional, o access logger do Uvicorn
remove por inteiro a query string de qualquer chamada recebida no endpoint de
callback, inclusive tentativas legadas por `GET`. Não habilite logging de corpo
HTTP em proxies ou observabilidade para esse endpoint.
