import { FileSearch, Search } from "lucide-react";
import { useCallback, useMemo, useState } from "react";

import { EmptyState, ErrorState, LoadingState } from "@/components/common/DataStates";
import { PageHeader } from "@/components/common/PageHeader";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useAsyncData } from "@/hooks/useAsyncData";
import { formatDate, formatMoney, formatPercent } from "@/lib/formatters";
import { fundingService } from "@/services/fundingService";

export function ContractsPage() {
  const loader = useCallback(() => fundingService.contracts.listContracts(), []);
  const { state, reload } = useAsyncData(loader);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const contracts = useMemo(() => state.status === "success" ? state.data : [], [state]);
  const filtered = useMemo(() => contracts.filter((item) => (item.code.toLowerCase().includes(search.toLowerCase()) || item.maskedClientName.toLowerCase().includes(search.toLowerCase())) && (status === "all" || item.status === status)), [contracts, search, status]);
  return <div className="space-y-6"><PageHeader eyebrow="Fonte operacional futura" title="Contratos" description="Visualização somente leitura com registros fictícios, preparada para uma futura integração controlada." actions={<Badge variant="outline">Clientes mascarados</Badge>} />
    <Card className="bg-card/75"><CardContent className="grid gap-3 p-4 md:grid-cols-[1fr_220px]"><label className="relative"><Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" /><span className="sr-only">Buscar contrato</span><Input className="pl-9" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Buscar código ou cliente mascarado…" /></label><Select value={status} onChange={(event) => setStatus(event.target.value)} aria-label="Status do funding"><option value="all">Todos os status</option><option value="available">Disponível</option><option value="partial">Funding parcial</option><option value="funded">Financiado</option></Select></CardContent></Card>
    {state.status === "loading" && <LoadingState />}{state.status === "error" && <ErrorState message={state.error} onRetry={reload} />}{state.status === "success" && (filtered.length === 0 ? <EmptyState /> : <Card className="overflow-hidden bg-card/75"><Table><TableHeader><TableRow><TableHead>Contrato</TableHead><TableHead>Cliente</TableHead><TableHead>Operação</TableHead><TableHead>Principal</TableHead><TableHead>Parcela</TableHead><TableHead>Prazo / taxa</TableHead><TableHead>Funding</TableHead><TableHead>Financiado</TableHead><TableHead>Status</TableHead></TableRow></TableHeader><TableBody>{filtered.map((item) => <TableRow key={item.id}><TableCell><div className="flex items-center gap-2"><FileSearch className="size-4 text-primary" /><span className="font-medium">{item.code}</span></div></TableCell><TableCell>{item.maskedClientName}</TableCell><TableCell><p>{formatDate(item.operationDate)}</p><p className="text-xs text-muted-foreground">Liberado {formatMoney(item.releasedAmount)}</p></TableCell><TableCell>{formatMoney(item.principalAmount)}</TableCell><TableCell>{formatMoney(item.installmentAmount)}</TableCell><TableCell>{item.termMonths} meses<br /><span className="text-xs text-muted-foreground">{formatPercent(item.monthlyRate)} a.m.</span></TableCell><TableCell><p>{formatMoney(item.allocatedFunding)}</p><p className="text-xs text-muted-foreground">de {formatMoney(item.requiredFunding)}</p></TableCell><TableCell><div className="w-28"><div className="mb-1 text-xs font-medium">{formatPercent(item.fundedPercent)}</div><div className="h-1.5 overflow-hidden rounded bg-muted"><div className="h-full bg-primary" style={{ width: `${Number(item.fundedPercent)}%` }} /></div></div></TableCell><TableCell><StatusBadge status={item.status} /></TableCell></TableRow>)}</TableBody></Table></Card>)}
  </div>;
}
