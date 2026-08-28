import { AlertTriangle, ArrowLeft, Banknote, Landmark, ReceiptText } from "lucide-react";
import { useCallback, useState } from "react";

import { AppLink } from "@/components/app/AppLink";
import { ErrorState, LoadingState } from "@/components/common/DataStates";
import { FeedbackBanner, type Feedback } from "@/components/common/FeedbackBanner";
import { KpiCard } from "@/components/common/KpiCard";
import { PageHeader } from "@/components/common/PageHeader";
import { StatusBadge } from "@/components/common/StatusBadge";
import { RevenueFundingPanel } from "@/components/funding/RevenueFundingPanel";
import { Card, CardContent } from "@/components/ui/card";
import { useAsyncData } from "@/hooks/useAsyncData";
import { formatDate } from "@/lib/formatters";
import { formatOperationalMoney } from "@/lib/operationalFormat";
import { fundingApi } from "@/services/fundingApi";
import { getRevenueDetail } from "@/services/operationalApi";
import type { QualityMessage } from "@/types/operational";

const bankValidationLabels = {
  NOT_RECORDED: "Pendente",
  VALIDATED: "Validado",
  DIVERGENT: "Divergente",
} as const;

export function RevenueDetailPage({ id, navigate }: { id: string; navigate: (path: string) => void }) {
  const loader = useCallback(async () => {
    const row = await getRevenueDetail(id);
    const distribution = await fundingApi.getRevenueDistribution(row.revenue_identity_id ?? id);
    return { row, distribution };
  }, [id]);
  const { state, reload } = useAsyncData(loader);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  if (state.status === "loading") return <LoadingState label="Carregando registro de Receita…" />;
  if (state.status === "error") return <ErrorState message={state.error} onRetry={reload} />;
  const { row, distribution } = state.data;
  const distribute = async () => { const notes = window.prompt("Observações do rateio (opcional):"); setSaving(true); try { await fundingApi.distributeRevenue(row.revenue_identity_id ?? id, { notes: notes?.trim() || null }); setFeedback({ tone: "success", message: "Rateio processado e retorno de principal registrado atomicamente." }); reload(); } catch (error) { setFeedback({ tone: "error", message: error instanceof Error ? error.message : "Falha ao processar rateio." }); } finally { setSaving(false); } };
  const reverse = async () => { if (!distribution.id) return; const reason = window.prompt("Motivo da reversão do rateio:"); if (!reason?.trim()) return; setSaving(true); try { await fundingApi.reverseRevenueDistribution(distribution.id, { reason: reason.trim() }); setFeedback({ tone: "success", message: "Rateio revertido por eventos compensatórios no ledger." }); reload(); } catch (error) { setFeedback({ tone: "error", message: error instanceof Error ? error.message : "Falha ao reverter rateio." }); } finally { setSaving(false); } };
  return <div className="space-y-6"><AppLink to="/receita" onNavigate={navigate} className="inline-flex items-center gap-2 text-sm text-muted-foreground"><ArrowLeft className="size-4" />Voltar para Receita</AppLink><PageHeader eyebrow="Receita operacional" title={`${row.contract_code ?? "Contrato não informado"} · parcela ${row.installment_code ?? "—"}`} description={row.client_name ?? "Não informado"} actions={<><StatusBadge status={row.installment_status === "REFIN" ? "REFIN" : row.data_quality_status} /><StatusBadge status={row.bank_validation_status} /></>} /><FeedbackBanner feedback={feedback} onClose={() => setFeedback(null)} /><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><KpiCard compact icon={ReceiptText} label="Valor esperado" value={formatOperationalMoney(row.expected_amount)} /><KpiCard compact icon={Banknote} label="Valor pago" value={formatOperationalMoney(row.paid_amount)} /><KpiCard compact icon={Landmark} label="Valor Principal" value={formatOperationalMoney(row.principal_component)} /><KpiCard compact icon={AlertTriangle} label="Avisos / divergências" value={`${row.warning_count} / ${row.divergence_count}`} /></div><RevenueFundingPanel distribution={distribution} saving={saving} onDistribute={distribute} onReverse={reverse} />{row.installment_status === "REFIN" && <Card className="border-cyan-400/30 bg-cyan-400/5"><CardContent className="p-5"><StatusBadge status="REFIN" /><p className="mt-2 text-sm">Saldo encerrado no cronograma anterior por refinanciamento{row.refinanced_to_contract_code ? ` para o contrato ${row.refinanced_to_contract_code}` : ""}. Não representa recebimento.</p></CardContent></Card>}<Card className="bg-card/75"><CardContent className="p-5"><p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Observação operacional</p><p className="mt-2 whitespace-pre-wrap text-sm">{row.anticipation_marker ?? "Não informado"}</p></CardContent></Card><InfoGrid rows={[["Código de Contrato", row.contract_code ?? "Não informado"], ["Nome do Cliente", row.client_name ?? "Não informado"], ["Parcela", row.installment_code ?? "Não informada"], ["Vencimento", formatDate(row.due_date)], ["Data da baixa", formatDate(row.payment_date)], ["Juros", formatOperationalMoney(row.interest_component)], ["Desconto", formatOperationalMoney(row.discount_amount)], ["Status da parcela", row.installment_status ?? "Não informado"], ["Situação", row.situation ?? "Não informada"], ["Marcador BAIXA_TOTAL", row.payment_marker ?? "Vazio"], ["Funding", row.funding_status ?? "Não vinculado"], ["Validação Bancária", bankValidationLabels[row.bank_validation_status]]]} /><QualityPanel warnings={row.warnings} divergences={row.divergences} /></div>;
}

function InfoGrid({ rows }: { rows: [string, string][] }) {
  return <Card className="bg-card/75"><CardContent className="grid gap-4 p-6 sm:grid-cols-2 xl:grid-cols-3">{rows.map(([label, value]) => <div key={label}><p className="text-xs uppercase tracking-wider text-muted-foreground">{label}</p><p className="mt-1 text-sm font-medium">{value}</p></div>)}</CardContent></Card>;
}

function QualityPanel({ warnings, divergences }: { warnings: QualityMessage[]; divergences: QualityMessage[] }) {
  return <div className="grid gap-4 lg:grid-cols-2"><Card className="bg-card/75"><CardContent className="p-6"><h2 className="font-semibold text-amber-400">Avisos ({warnings.length})</h2><div className="mt-3 space-y-2 text-sm">{warnings.length ? warnings.map((item, index) => <p key={`${item.type}-${index}`}>{item.message}</p>) : <p className="text-muted-foreground">Nenhum aviso.</p>}</div></CardContent></Card><Card className="border-rose-400/30 bg-card/75"><CardContent className="p-6"><h2 className="font-semibold text-rose-400">Divergências ({divergences.length})</h2><div className="mt-3 space-y-2 text-sm">{divergences.length ? divergences.map((item, index) => <p key={`${item.type}-${index}`}>{item.message}</p>) : <p className="text-muted-foreground">Nenhuma divergência.</p>}</div></CardContent></Card></div>;
}
