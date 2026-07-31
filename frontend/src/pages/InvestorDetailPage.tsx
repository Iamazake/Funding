import { ArrowLeft, Banknote, CalendarClock, CircleDollarSign, Landmark } from "lucide-react";
import { useCallback } from "react";

import { AppLink } from "@/components/app/AppLink";
import { ChartCard } from "@/components/charts/FundingCharts";
import { EmptyState, ErrorState, LoadingState } from "@/components/common/DataStates";
import { KpiCard } from "@/components/common/KpiCard";
import { PageHeader } from "@/components/common/PageHeader";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useAsyncData } from "@/hooks/useAsyncData";
import { formatDate, formatMoney, formatPercent } from "@/lib/formatters";
import { fundingService } from "@/services/fundingService";

export function InvestorDetailPage({ id, navigate }: { id: string; navigate: (path: string) => void }) {
  const loader = useCallback(() => fundingService.investors.getInvestor(id), [id]);
  const { state, reload } = useAsyncData(loader);
  if (state.status === "loading") return <LoadingState />;
  if (state.status === "error") return <ErrorState message={state.error} onRetry={reload} />;
  if (!state.data) return <EmptyState title="Investidor não encontrado" action={<Button onClick={() => navigate("/investidores")}>Voltar à lista</Button>} />;
  const investor = state.data;
  return <div className="space-y-6">
    <AppLink to="/investidores" onNavigate={navigate} className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="size-4" />Voltar para investidores</AppLink>
    <PageHeader eyebrow="Posição individual" title={investor.name} description={`${investor.maskedDocument} · ${investor.email}`} actions={<StatusBadge status={investor.status} />} />
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><KpiCard compact icon={CircleDollarSign} label="Capital aportado" value={formatMoney(investor.contributedCapital)} /><KpiCard compact icon={Banknote} label="Saldo livre" value={formatMoney(investor.availableBalance)} /><KpiCard compact icon={Landmark} label="Saldo alocado" value={formatMoney(investor.allocatedBalance)} /><KpiCard compact icon={CalendarClock} label="Próximo pagamento" value={formatMoney(investor.nextPaymentAmount)} helper={formatDate(investor.nextPaymentDate)} /></div>
    <div className="grid gap-5 xl:grid-cols-[1.4fr_1fr]"><ChartCard title="Evolução da posição" description="Índice visual demonstrativo, sem cálculo financeiro definitivo" data={investor.evolution} /><Card className="bg-card/75"><CardHeader><CardTitle className="text-base">Dados gerais fictícios</CardTitle></CardHeader><CardContent className="space-y-4 text-sm"><Detail label="Ingresso" value={formatDate(investor.joinedAt)} /><Detail label="Documento" value={investor.maskedDocument} /><Detail label="Remuneração acumulada" value={formatMoney(investor.accumulatedReturn)} /><Detail label="Ambiente" value="Somente demonstração" /></CardContent></Card></div>
    <section><h2 className="mb-3 text-lg font-semibold">Aportes</h2><Card className="overflow-hidden bg-card/75"><Table><TableHeader><TableRow><TableHead>Código</TableHead><TableHead>Original</TableHead><TableHead>Disponível</TableHead><TableHead>Alocado</TableHead><TableHead>Taxa mensal</TableHead><TableHead>Vigência</TableHead></TableRow></TableHeader><TableBody>{investor.contributions.map((item) => <TableRow key={item.id}><TableCell className="font-medium">{item.code}</TableCell><TableCell>{formatMoney(item.originalAmount)}</TableCell><TableCell>{formatMoney(item.availableAmount)}</TableCell><TableCell>{formatMoney(item.allocatedAmount)}</TableCell><TableCell>{formatPercent(item.monthlyRate)}</TableCell><TableCell>{formatDate(item.startDate)} – {formatDate(item.endDate)}</TableCell></TableRow>)}</TableBody></Table></Card></section>
    <div className="grid gap-5 xl:grid-cols-2"><HistoryTable title="Alocações" headers={["Contrato", "Valor", "Data"]} rows={investor.allocations.map((item) => [item.contractCode, formatMoney(item.amount), formatDate(item.allocatedAt)])} /><HistoryTable title="Próximas remunerações" headers={["Referência", "Valor", "Vencimento"]} rows={investor.remunerations.map((item) => [item.reference, formatMoney(item.amount), formatDate(item.dueDate)])} /></div>
    <HistoryTable title="Histórico de movimentações" headers={["Data", "Descrição", "Valor", "Status"]} rows={investor.movements.map((item) => [formatDate(item.date), item.description, formatMoney(item.amount), item.status === "completed" ? "Concluído" : "Programado"])} />
  </div>;
}

function Detail({ label, value }: { label: string; value: string }) { return <div className="flex items-center justify-between gap-4 border-b border-border/60 pb-3 last:border-0 last:pb-0"><span className="text-muted-foreground">{label}</span><span className="text-right font-medium">{value}</span></div>; }
function HistoryTable({ title, headers, rows }: { title: string; headers: string[]; rows: string[][] }) { return <section><h2 className="mb-3 text-lg font-semibold">{title}</h2><Card className="overflow-hidden bg-card/75"><Table><TableHeader><TableRow>{headers.map((header) => <TableHead key={header}>{header}</TableHead>)}</TableRow></TableHeader><TableBody>{rows.map((row, index) => <TableRow key={`${title}-${index}`}>{row.map((cell, cellIndex) => <TableCell key={`${title}-${index}-${cellIndex}`}>{cell}</TableCell>)}</TableRow>)}</TableBody></Table></Card></section>; }
