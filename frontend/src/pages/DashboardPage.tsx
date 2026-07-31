import { Banknote, BriefcaseBusiness, CalendarClock, CircleDollarSign, Landmark, TrendingUp } from "lucide-react";
import { useCallback, useState } from "react";

import { ChartCard } from "@/components/charts/FundingCharts";
import { KpiCard } from "@/components/common/KpiCard";
import { LoadingState, ErrorState } from "@/components/common/DataStates";
import { PageHeader } from "@/components/common/PageHeader";
import { PeriodSelector } from "@/components/common/PeriodSelector";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAsyncData } from "@/hooks/useAsyncData";
import { formatDate, formatMoney } from "@/lib/formatters";
import { fundingService } from "@/services/fundingService";

const metricIcons = [CircleDollarSign, Banknote, Landmark, BriefcaseBusiness, TrendingUp, CalendarClock];

export function DashboardPage() {
  const [period, setPeriod] = useState("180");
  const loader = useCallback(() => fundingService.dashboard.getDashboard(), []);
  const { state, reload } = useAsyncData(loader);

  if (state.status === "loading") return <LoadingState label="Preparando visão executiva demonstrativa…" />;
  if (state.status === "error") return <ErrorState message={state.error} onRetry={reload} />;
  const data = state.data;

  return <div className="space-y-6 sm:space-y-8">
    <PageHeader eyebrow="Visão executiva" title="Dashboard de funding" description="Acompanhe a posição consolidada do capital demonstrativo, sua alocação e a agenda projetada." actions={<PeriodSelector value={period} onChange={setPeriod} />} />
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{data.metrics.map((metric, index) => <KpiCard key={metric.id} label={metric.label} value={formatMoney(metric.value)} variation={metric.variationPercent} direction={metric.direction} icon={metricIcons[index]} helper="comparado ao mês demonstrativo anterior" />)}</div>
    <div className="grid gap-5 xl:grid-cols-[1.6fr_1fr]"><ChartCard title="Evolução do funding" description="Capital captado e alocado · valores em milhares de reais" data={data.fundingEvolution} /><ChartCard title="Disponível versus alocado" description="Posição atual demonstrativa · R$ mil" data={data.capitalPosition} variant="donut" /></div>
    <div className="grid gap-5 xl:grid-cols-[1.2fr_1fr]"><ChartCard title="Distribuição por investidor" description="Capital aportado demonstrativo · R$ mil" data={data.investorDistribution} variant="bar" />
      <Card className="bg-card/75"><CardHeader><CardTitle className="text-base">Vencimentos futuros</CardTitle></CardHeader><CardContent className="space-y-3">{data.upcomingPayments.map((payment) => <div key={payment.id} className="flex items-center justify-between gap-3 rounded-xl border border-border bg-background/35 p-4"><div className="min-w-0"><p className="truncate text-sm font-medium">{payment.investorName}</p><p className="mt-1 text-xs text-muted-foreground">{formatDate(payment.dueDate)} · Remuneração</p></div><p className="shrink-0 text-sm font-semibold">{formatMoney(payment.amount)}</p></div>)}</CardContent></Card>
    </div>
    <Card className="bg-card/75"><CardHeader><CardTitle className="text-base">Atividades recentes</CardTitle></CardHeader><CardContent><div className="grid gap-3 md:grid-cols-3">{data.recentActivities.map((activity) => <div key={activity.id} className="rounded-xl border border-border bg-background/35 p-4"><div className="flex items-center justify-between gap-2"><Badge variant={activity.tone}>{activity.title}</Badge><span className="text-[11px] text-muted-foreground">{formatDate(activity.occurredAt)}</span></div><p className="mt-3 text-sm leading-6 text-muted-foreground">{activity.description}</p></div>)}</div></CardContent></Card>
  </div>;
}
