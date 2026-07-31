import { ArrowLeft, Banknote, CalendarDays, CircleDollarSign, Percent } from "lucide-react";
import { useCallback } from "react";

import { AppLink } from "@/components/app/AppLink";
import { EmptyState, ErrorState, LoadingState } from "@/components/common/DataStates";
import { KpiCard } from "@/components/common/KpiCard";
import { PageHeader } from "@/components/common/PageHeader";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAsyncData } from "@/hooks/useAsyncData";
import { formatDate, formatMoney, formatPercent } from "@/lib/formatters";
import { fundingService } from "@/services/fundingService";

export function ContributionDetailPage({ id, navigate }: { id: string; navigate: (path: string) => void }) {
  const loader = useCallback(() => fundingService.contributions.getContribution(id), [id]);
  const { state, reload } = useAsyncData(loader);
  if (state.status === "loading") return <LoadingState />;
  if (state.status === "error") return <ErrorState message={state.error} onRetry={reload} />;
  if (!state.data) return <EmptyState title="Aporte não encontrado" action={<Button onClick={() => navigate("/aportes")}>Voltar</Button>} />;
  const item = state.data;
  return <div className="space-y-6"><AppLink to="/aportes" onNavigate={navigate} className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="size-4" />Voltar para aportes</AppLink><PageHeader eyebrow="Detalhe do aporte" title={item.code} description={`Capital demonstrativo de ${item.investorName}.`} actions={<StatusBadge status={item.status} />} />
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><KpiCard compact icon={CircleDollarSign} label="Valor original" value={formatMoney(item.originalAmount)} /><KpiCard compact icon={Banknote} label="Saldo disponível" value={formatMoney(item.availableAmount)} /><KpiCard compact icon={Percent} label="Taxa mensal" value={formatPercent(item.monthlyRate)} /><KpiCard compact icon={CalendarDays} label="Vigência" value={formatDate(item.endDate)} helper={`Início em ${formatDate(item.startDate)}`} /></div>
    <Card className="bg-card/75"><CardHeader><CardTitle className="text-base">Posição demonstrativa</CardTitle></CardHeader><CardContent><div className="h-3 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full bg-gradient-to-r from-cyan-400 to-indigo-500" style={{ width: `${Math.min(100, Number(item.allocatedAmount) / Number(item.originalAmount) * 100)}%` }} /></div><div className="mt-4 flex justify-between text-sm"><span className="text-muted-foreground">Alocado</span><span className="font-semibold">{formatMoney(item.allocatedAmount)}</span></div><p className="mt-6 rounded-xl border border-primary/15 bg-primary/5 p-4 text-sm leading-6 text-muted-foreground">Todos os valores desta página são fictícios. Taxa, vigência e remuneração não constituem cálculo financeiro definitivo.</p></CardContent></Card>
  </div>;
}
