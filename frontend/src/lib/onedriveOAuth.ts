const oauthErrorMessages: Record<string, string> = {
  invalid_client_secret:
    "O client secret Microsoft é inválido. Use o Value do secret, não o Secret ID.",
  client_secret_expired:
    "O client secret Microsoft expirou. Cadastre um novo valor no ambiente.",
  redirect_uri_mismatch:
    "O redirect URI não corresponde ao valor registrado no Microsoft Entra.",
  authorization_code_invalid:
    "O código de autorização expirou ou já foi utilizado. Tente conectar novamente.",
  token_exchange_failed: "Não foi possível trocar o código de autorização Microsoft.",
  token_exchange_exception: "Não foi possível concluir a autorização Microsoft.",
  graph_auth_failed: "A autorização do Microsoft Graph não foi aceita.",
  graph_permission_denied: "A conta Microsoft não permitiu a leitura do OneDrive.",
  graph_drive_failed: "Não foi possível consultar a estrutura do OneDrive.",
  file_not_found: "O arquivo oficial configurado não foi encontrado no OneDrive.",
  access_denied: "A autorização Microsoft foi cancelada.",
  consent_required: "A conta Microsoft ainda não concedeu a permissão Files.Read.",
  configuration_error: "A configuração administrativa do OneDrive está incompleta.",
};

export function onedriveOAuthErrorMessage(code: string | null): string {
  if (code && oauthErrorMessages[code]) return oauthErrorMessages[code];
  return "Não foi possível concluir a autorização Microsoft.";
}
