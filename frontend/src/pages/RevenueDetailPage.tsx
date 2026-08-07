import { AlertTriangle, ArrowLeft, Banknote, Landmark, ReceiptText } from "lucide-react";
import { useCallback } from "react";

import { AppLink } from "@/components/app/AppLink";
import { ErrorState, LoadingState } from "@/components/common/DataStates";
import { KpiCard } from "@/components/common/KpiCard";
import { PageHeader } from "@/components/common/PageHeader";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Card, CardContent } from "@/components/ui/card";
import { useAsyncData } from "@/hooks/useAsyncData";
import { formatDate } from "@/lib/formatters";
import { formatOperationalMoney } from "@/lib/operationalFormat";
import { getRevenueDetail } from "@/services/operationalApi";
import type { QualityMessage } from "@/types/operational";

export function RevenueDetailPage({ id, navigate }: { id: string; navigate: (path: string) => void }) {
  const loader = useCallback(() => getRevenueDetail(id), [id]);
  const { state, reload } = useAsyncData(loader);
  if (state.status === "loading") return <LoadingState label="Carregando registro de Receita…" />;
  if (state.status === "error") return <ErrorState message={state.error} onRetry={reload} />;
  const row = state.data;
  return <div className="space-y-6"><AppLink to="/receita" onNavigate={navigate} className="inline-flex items-center gap-2 text-sm text-muted-foreground"><ArrowLeft className="size-4" />Voltar para Receita</AppLink><PageHeader eyebrow="Receita operacional" title={`${row.contract_code ?? "Contrato não informado"} · parcela ${row.installment_code ?? "—"}`} description={row.client_name ?? "Cliente não resolvido na promoção atual."} actions={<StatusBadge status={row.data_quality_status} />} /><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><KpiCard compact icon={ReceiptText} label="Valor esperado" value={formatOperationalMoney(row.expected_amount)} /><KpiCard compact icon={Banknote} label="Valor pago" value={formatOperationalMoney(row.paid_amount)} /><KpiCard compact icon={Landmark} label="Principal" value={formatOperationalMoney(row.principal_component)} /><KpiCard compact icon={AlertTriangle} label="Avisos / divergências" value={`${row.warning_count} / ${row.divergence_count}`} /></div><InfoGrid rows={[["Contrato", row.contract_code ?? "Não informado"], ["Cliente", row.client_name ?? "Não resolvido"], ["Parcela", row.installment_code ?? "Não informada"], ["Vencimento", formatDate(row.due_date)], ["Data da baixa", formatDate(row.payment_date)], ["Juros", formatOperationalMoney(row.interest_component)], ["Desconto", formatOperationalMoney(row.discount_amount)], ["Status da parcela", row.installment_status ?? "Não informado"], ["Situação", row.situation ?? "Não informada"], ["Antecipação", row.anticipation_marker ?? "Não informada"], ["Marcador BAIXA_TOTAL", row.payment_marker ?? "Vazio"], ["Referência operacional", row.source_reference ?? "Não informada"], ["Funding", "Ainda não informado"], ["Validação bancária", "Pendente / não registrada"]]} /><QualityPanel warnings={row.warnings} divergences={row.divergences} /></div>;
}

function InfoGrid({ rows }: { rows: [string, string][] }) {
  return <Card className="bg-card/75"><CardContent className="grid gap-4 p-6 sm:grid-cols-2 xl:grid-cols-3">{rows.map(([label, value]) => <div key={label}><p className="text-xs uppercase tracking-wider text-muted-foreground">{label}</p><p className="mt-1 text-sm font-medium">{value}</p></div>)}</CardContent></Card>;
}

function QualityPanel({ warnings, divergences }: { warnings: QualityMessage[]; divergences: QualityMessage[] }) {
  return <div className="grid gap-4 lg:grid-cols-2"><Card className="bg-card/75"><CardContent className="p-6"><h2 className="font-semibold text-amber-400">Avisos ({warnings.length})</h2><div className="mt-3 space-y-2 text-sm">{warnings.length ? warnings.map((item, index) => <p key={`${item.type}-${index}`}>{item.message}</p>) : <p className="text-muted-foreground">Nenhum aviso.</p>}</div></CardContent></Card><Card className="border-rose-400/30 bg-card/75"><CardContent className="p-6"><h2 className="font-semibold text-rose-400">Divergências ({divergences.length})</h2><div className="mt-3 space-y-2 text-sm">{divergences.length ? divergences.map((item, index) => <p key={`${item.type}-${index}`}>{item.message}</p>) : <p className="text-muted-foreground">Nenhuma divergência.</p>}</div></CardContent></Card></div>;
}
