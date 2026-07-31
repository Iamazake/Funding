import { Download, FileChartColumn } from "lucide-react";
import { useCallback, useState } from "react";

import { ChartCard } from "@/components/charts/FundingCharts";
import { ErrorState, LoadingState } from "@/components/common/DataStates";
import { PageHeader } from "@/components/common/PageHeader";
import { PeriodSelector } from "@/components/common/PeriodSelector";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useAsyncData } from "@/hooks/useAsyncData";
import { formatDate } from "@/lib/formatters";
import { fundingService } from "@/services/fundingService";

export function ReportsPage() {
  const loader = useCallback(() => fundingService.treasury.getReports(), []);
  const { state, reload } = useAsyncData(loader);
  const [period, setPeriod] = useState("180");
  if (state.status === "loading") return <LoadingState />;
  if (state.status === "error") return <ErrorState message={state.error} onRetry={reload} />;
  const data = state.data;
  return <div className="space-y-6"><PageHeader eyebrow="Análises demonstrativas" title="Relatórios" description="Painéis visuais para explorar funding, retorno, remunerações, tesouraria e contratos." actions={<><PeriodSelector value={period} onChange={setPeriod} /><Button variant="outline" disabled title="Exportação disponível em etapa futura"><Download className="size-4" />Exportar</Button></>} />
    <Card className="border-primary/20 bg-primary/5"><CardContent className="flex items-center justify-between gap-4 p-4"><div className="flex items-center gap-3"><FileChartColumn className="size-5 text-primary" /><div><p className="text-sm font-medium">Relatório demonstrativo</p><p className="text-xs text-muted-foreground">Posição de referência em {formatDate(data.generatedAt)}</p></div></div><Badge variant="outline">Sem valor contábil</Badge></CardContent></Card>
    <div className="grid gap-5 xl:grid-cols-2"><ChartCard title="Funding por investidor" description="Capital fictício por participante · R$ mil" data={data.fundingByInvestor} variant="bar" /><ChartCard title="Retorno por investidor" description="Retorno acumulado fictício · R$ mil" data={data.returnByInvestor} variant="bar" /><ChartCard title="Capital disponível e alocado" description="Posição consolidada demonstrativa · R$ mil" data={data.capitalPosition} variant="donut" /><ChartCard title="Remuneração prevista" description="Projeção visual sem cálculo definitivo · R$ mil" data={data.remunerationForecast} /><ChartCard title="Movimentações de tesouraria" description="Distribuição demonstrativa por tipo · R$ mil" data={data.treasuryByType} variant="bar" /><ChartCard title="Distribuição por contrato" description="Percentual visual da carteira fictícia" data={data.contractDistribution} variant="donut" /></div>
  </div>;
}
