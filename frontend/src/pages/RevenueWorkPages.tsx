import { useCallback } from "react";

import { AppLink } from "@/components/app/AppLink";
import { EmptyState, ErrorState, LoadingState } from "@/components/common/DataStates";
import { PageHeader } from "@/components/common/PageHeader";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Card } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useAsyncData } from "@/hooks/useAsyncData";
import { formatDate } from "@/lib/formatters";
import { formatOperationalMoney } from "@/lib/operationalFormat";
import { getRevenue } from "@/services/operationalApi";

export function RevenuePendingPage({ navigate }: { navigate: (path: string) => void }) {
  return <div className="space-y-6"><PageHeader eyebrow="Receita" title="Pendências" description="A fila operacional real de conciliação bancária ainda não foi integrada." /><EmptyState title="Pendente / não registrada" description="Consulte as parcelas reais em Receita. Nenhum movimento bancário ou funding fictício será associado a elas." action={<AppLink to="/receita" onNavigate={navigate} className="text-primary">Abrir Receita operacional</AppLink>} /></div>;
}

export function RevenueDivergencesPage({ navigate }: { navigate: (path: string) => void }) {
  const loader = useCallback(() => getRevenue({ page: 1, page_size: 100, quality: "DIVERGENT" }), []);
  const { state, reload } = useAsyncData(loader);
  return <div className="space-y-6"><PageHeader eyebrow="Receita" title="Divergências operacionais" description="Parcelas órfãs preservadas pela promoção atual." />{state.status === "loading" ? <LoadingState /> : state.status === "error" ? <ErrorState message={state.error} onRetry={reload} /> : state.data.items.length === 0 ? <EmptyState /> : <Card className="overflow-hidden bg-card/75"><Table><TableHeader><TableRow><TableHead>Contrato</TableHead><TableHead>Parcela</TableHead><TableHead>Vencimento</TableHead><TableHead>Pago</TableHead><TableHead>Qualidade</TableHead><TableHead>Motivos</TableHead></TableRow></TableHeader><TableBody>{state.data.items.map((row) => <TableRow key={row.id} className="cursor-pointer" onClick={() => navigate(`/receita/${row.id}`)}><TableCell><AppLink to={`/receita/${row.id}`} onNavigate={navigate} className="font-medium text-primary">{row.contract_code ?? "Não informado"}</AppLink></TableCell><TableCell>{row.installment_code ?? "—"}</TableCell><TableCell>{formatDate(row.due_date)}</TableCell><TableCell>{formatOperationalMoney(row.paid_amount)}</TableCell><TableCell><StatusBadge status={row.data_quality_status} /></TableCell><TableCell>{row.divergence_count} divergência(s)</TableCell></TableRow>)}</TableBody></Table></Card>}</div>;
}

export function RevenueMonthlySummaryPage() {
  return <div className="space-y-6"><PageHeader eyebrow="Receita" title="Resumo mensal" description="A agregação mensal real não faz parte desta integração inicial." /><EmptyState title="Resumo real ainda não disponível" description="Nenhum relatório demonstrativo é exibido para evitar mistura com as parcelas operacionais reais." /></div>;
}
