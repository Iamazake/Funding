import { ArrowDownLeft, ArrowUpRight, Landmark, PiggyBank, RefreshCw, Wallet } from "lucide-react";
import { useCallback, useMemo, useState } from "react";

import { EmptyState, ErrorState, LoadingState } from "@/components/common/DataStates";
import { KpiCard } from "@/components/common/KpiCard";
import { PageHeader } from "@/components/common/PageHeader";
import { PeriodSelector } from "@/components/common/PeriodSelector";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Card, CardContent } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useAsyncData } from "@/hooks/useAsyncData";
import { formatDate, formatMoney } from "@/lib/formatters";
import { cn } from "@/lib/utils";
import { fundingService } from "@/services/fundingService";

const movementLabels = { contribution: "Aporte", allocation: "Alocação", remuneration: "Remuneração", refund: "Devolução", reinvestment: "Reinvestimento", pjr: "PJR" } as const;

export function TreasuryPage() {
  const loader = useCallback(() => fundingService.treasury.getTreasury(), []);
  const { state, reload } = useAsyncData(loader);
  const [period, setPeriod] = useState("90");
  const [investor, setInvestor] = useState("all");
  const [type, setType] = useState("all");
  const data = state.status === "success" ? state.data : null;
  const investors = useMemo(() => data ? Array.from(new Map(data.movements.map((item) => [item.investorId, item.investorName])).entries()) : [], [data]);
  const movements = useMemo(() => data?.movements.filter((item) => (investor === "all" || item.investorId === investor) && (type === "all" || item.type === type)) ?? [], [data, investor, type]);
  if (state.status === "loading") return <LoadingState />;
  if (state.status === "error") return <ErrorState message={state.error} onRetry={reload} />;
  if (!data) return null;
  return <div className="space-y-6"><PageHeader eyebrow="Movimentação de capital" title="Tesouraria" description="Visão demonstrativa de entradas, saídas, remunerações, devoluções, reinvestimentos e PJR." actions={<PeriodSelector value={period} onChange={setPeriod} />} />
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><KpiCard compact icon={Landmark} label="Saldo geral" value={formatMoney(data.generalBalance)} /><KpiCard compact icon={ArrowDownLeft} label="Entradas" value={formatMoney(data.totalInflows)} /><KpiCard compact icon={ArrowUpRight} label="Saídas" value={formatMoney(data.totalOutflows)} /><KpiCard compact icon={PiggyBank} label="Remunerações" value={formatMoney(data.totalRemuneration)} /></div>
    <div className="grid gap-4 sm:grid-cols-3"><KpiCard compact icon={Wallet} label="Devoluções" value={formatMoney(data.totalRefunds)} /><KpiCard compact icon={RefreshCw} label="Reinvestimentos" value={formatMoney(data.totalReinvestments)} /><KpiCard compact icon={Landmark} label="PJR demonstrativo" value={formatMoney(data.totalPjr)} helper="Parâmetros ainda a definir" /></div>
    <Card className="bg-card/75"><CardContent className="grid gap-3 p-4 md:grid-cols-2"><Select value={investor} onChange={(event) => setInvestor(event.target.value)} aria-label="Filtrar investidor"><option value="all">Todos os investidores</option>{investors.map(([id, name]) => <option key={id} value={id}>{name}</option>)}</Select><Select value={type} onChange={(event) => setType(event.target.value)} aria-label="Filtrar tipo"><option value="all">Todos os tipos</option>{Object.entries(movementLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</Select></CardContent></Card>
    {movements.length === 0 ? <EmptyState /> : <Card className="overflow-hidden bg-card/75"><Table><TableHeader><TableRow><TableHead>Data</TableHead><TableHead>Tipo</TableHead><TableHead>Investidor</TableHead><TableHead>Descrição</TableHead><TableHead>Direção</TableHead><TableHead>Valor</TableHead><TableHead>Status</TableHead></TableRow></TableHeader><TableBody>{movements.map((item) => <TableRow key={item.id}><TableCell>{formatDate(item.date)}</TableCell><TableCell>{movementLabels[item.type]}</TableCell><TableCell>{item.investorName}</TableCell><TableCell className="text-muted-foreground">{item.description}</TableCell><TableCell><span className={cn("inline-flex items-center gap-1 text-xs font-medium", item.direction === "in" ? "text-emerald-400" : "text-amber-400")}>{item.direction === "in" ? <ArrowDownLeft className="size-3.5" /> : <ArrowUpRight className="size-3.5" />}{item.direction === "in" ? "Entrada" : "Saída"}</span></TableCell><TableCell className="font-medium">{formatMoney(item.amount)}</TableCell><TableCell><StatusBadge status={item.status} /></TableCell></TableRow>)}</TableBody></Table></Card>}
  </div>;
}
