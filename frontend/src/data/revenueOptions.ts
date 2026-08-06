import type { RevenueColumnKey, RevenueDivergenceType, RevenueStatus } from "@/types/funding";

export const revenueStatusLabels: Record<RevenueStatus, string> = {
  PENDING_OPERATIONAL_DATA: "Dados operacionais pendentes",
  PENDING_BANK_VALIDATION: "Validação bancária pendente",
  PENDING_ALLOCATION: "Rateio pendente",
  PARTIALLY_VALIDATED: "Validado parcialmente",
  VALIDATED: "Validado",
  COMPONENT_DIVERGENCE: "Componentes divergentes",
  BANK_DIVERGENCE: "Divergência bancária",
  REVERSED: "Estornado",
  CANCELLED: "Cancelado",
};

export const revenueDivergenceLabels: Record<RevenueDivergenceType, string> = {
  RECEIPT_COMPONENT_MISMATCH: "Componentes do recebimento não conferem",
  BANK_AMOUNT_MISMATCH: "Valor bancário divergente",
  BANK_MOVEMENT_NOT_FOUND: "Movimento bancário não encontrado",
  FUNDING_COMPOSITION_NOT_FOUND: "Composição de funding não encontrada",
  ALLOCATION_TOTAL_MISMATCH: "Total do rateio divergente",
  PARTIAL_PAYMENT: "Pagamento parcial",
  DUPLICATED_RECEIPT: "Recebimento duplicado",
  OPERATIONAL_STATUS_CONFLICT: "Conflito de status operacional",
  REVERSED_AFTER_ALLOCATION: "Estorno após rateio",
};

export const revenueColumnLabels: Record<RevenueColumnKey, string> = {
  contract: "Contrato e cliente", installment: "Parcela", dueDate: "Vencimento", paymentDate: "Pagamento",
  expected: "PMT prevista", paid: "Valor pago", status: "Status operacional", operator: "Operador financeiro",
  principal: "Principal", interest: "Juros", iof: "IOF", loss: "Prejuízo", discount: "Desconto",
  apurated: "Total apurado", componentDifference: "Diferença dos componentes", paymentReference: "Referência do pagamento",
  funding: "Fontes do funding", bankValidation: "Validação bancária", revenueStatus: "Status da receita",
};

export const requiredRevenueColumns: RevenueColumnKey[] = ["contract", "installment", "paid", "revenueStatus"];
