import { Badge } from "@/components/ui/badge";
const labels: Record<string, string> = {
  PENDENTE: "Pendente", ATIVO: "Ativo", INATIVO: "Inativo", ENCERRADO: "Encerrado", CANCELADO: "Cancelado",
  PARCIALMENTE_ALOCADO: "Parcialmente alocado", TOTALMENTE_ALOCADO: "Totalmente alocado", EM_LIQUIDACAO: "Em liquidação", LIQUIDADO: "Liquidado", LIQUIDADO_ANTECIPADAMENTE: "Liquidado antecipadamente",
  PREVISTA: "Prevista", A_VENCER: "A vencer", VENCE_HOJE: "Vence hoje", ATRASADA: "Atrasada", PAGA: "Paga", REINVESTIDA: "Reinvestida", QUITADA: "Quitada", CANCELADA: "Cancelada",
  DRAFT: "Rascunho", PENDING_FUNDING: "Funding pendente", FUNDING_DIVERGENT: "Funding divergente", FUNDED: "Com funding", RELEASED: "Liberado", CANCELLED: "Cancelado",
  WAITING_OPERATIONAL_WRITE_OFF: "Aguardando baixa operacional", WAITING_BANK_VALIDATION: "Aguardando validação bancária", BANK_MOVEMENT_FOUND: "Movimento encontrado", BANK_VALUE_MISMATCH: "Valor bancário divergente", BANK_MOVEMENT_NOT_FOUND: "Movimento não encontrado", PARTIALLY_VALIDATED: "Validada parcialmente", VALIDATED: "Validada", REVERSED: "Estornada",
  PENDING_OPERATIONAL_DATA: "Dados operacionais pendentes", PENDING_BANK_VALIDATION: "Validação bancária pendente", PENDING_ALLOCATION: "Rateio pendente", COMPONENT_DIVERGENCE: "Componentes divergentes", BANK_DIVERGENCE: "Divergência bancária",
  COMPONENTS_MATCH: "Componentes conferem", COMPONENTS_MISMATCH: "Componentes divergentes", COMPONENTS_INCOMPLETE: "Componentes incompletos",
  NOT_CALCULATED: "Não calculado", CALCULATED: "Calculado", DIVERGENT: "Divergente", REVIEW_REQUIRED: "Revisão necessária", CONFIRMED: "Confirmado", RULE_TO_CONFIRM: "Regra a confirmar",
  WAITING_WRITE_OFF: "Aguardando baixa", WRITTEN_OFF: "Baixada", PARTIAL: "Conciliação parcial", RECONCILED: "Conciliada", FOUND: "Encontrado", NOT_FOUND: "Não encontrado",
  PENDING: "Pendente", VALID: "Válido", MOVEMENT_FOUND: "Movimento encontrado", VALUE_MISMATCH: "Valor divergente", MOVEMENT_NOT_FOUND: "Movimento não encontrado", REJECTED: "Rejeitada",
  OPEN: "Aberta", IN_REVIEW: "Em análise", RESOLVED: "Resolvida", JUSTIFIED_EXCEPTION: "Exceção justificada",
  CONFIRMADO: "Confirmado", ESTORNADO: "Estornado", ENTRADA: "Entrada", SAIDA: "Saída", TRANSFERENCIA_INTERNA: "Transferência interna", CONCILIADO: "Conciliado",
  BAIXO: "Baixo", MEDIO: "Médio", ALTO: "Alto",
};

function statusLabel(status: string): string {
  return labels[status] ?? status.replaceAll("_", " ");
}

export function StatusBadge({ status }: { status: string }) {
  const good = ["ATIVO", "PAGA", "QUITADA", "VALID", "VALIDATED", "RESOLVED", "CONFIRMADO", "CONFIRMED", "CALCULATED", "COMPONENTS_MATCH", "CONCILIADO", "RECONCILED", "BAIXO", "FUNDED", "RELEASED", "WRITTEN_OFF", "FOUND"];
  const warn = ["PENDENTE", "PENDING", "A_VENCER", "VENCE_HOJE", "PARCIALMENTE_ALOCADO", "EM_LIQUIDACAO", "FUNDING_DIVERGENT", "OPEN", "IN_REVIEW", "MEDIO", "WAITING_OPERATIONAL_WRITE_OFF", "WAITING_BANK_VALIDATION", "PENDING_OPERATIONAL_DATA", "PENDING_BANK_VALIDATION", "PENDING_ALLOCATION", "PARTIALLY_VALIDATED", "PARTIAL", "NOT_CALCULATED", "REVIEW_REQUIRED", "COMPONENTS_INCOMPLETE", "RULE_TO_CONFIRM"];
  const danger = ["INATIVO", "CANCELADO", "CANCELADA", "CANCELLED", "ATRASADA", "ALTO", "VALUE_MISMATCH", "MOVEMENT_NOT_FOUND", "BANK_VALUE_MISMATCH", "BANK_MOVEMENT_NOT_FOUND", "BANK_DIVERGENCE", "COMPONENT_DIVERGENCE", "COMPONENTS_MISMATCH", "DIVERGENT", "REJECTED", "NOT_FOUND"];
  return <Badge variant={good.includes(status) ? "success" : warn.includes(status) ? "warning" : danger.includes(status) ? "danger" : "info"}>{statusLabel(status)}</Badge>;
}
