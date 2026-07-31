import { Eye, Filter, Plus, Search, WalletCards } from "lucide-react";
import { useCallback, useMemo, useState } from "react";

import { AppLink } from "@/components/app/AppLink";
import { EmptyState, ErrorState, LoadingState } from "@/components/common/DataStates";
import { Modal } from "@/components/common/Modal";
import { PageHeader } from "@/components/common/PageHeader";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useAsyncData } from "@/hooks/useAsyncData";
import { formatDate, formatMoney, formatPercent } from "@/lib/formatters";
import { fundingService } from "@/services/fundingService";

export function ContributionsPage({ navigate }: { navigate: (path: string) => void }) {
  const loader = useCallback(() => fundingService.contributions.listContributions(), []);
  const { state, reload } = useAsyncData(loader);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [modalOpen, setModalOpen] = useState(false);
  const contributions = useMemo(() => state.status === "success" ? state.data : [], [state]);
  const filtered = useMemo(() => contributions.filter((item) => (item.code.toLowerCase().includes(search.toLowerCase()) || item.investorName.toLowerCase().includes(search.toLowerCase())) && (status === "all" || item.status === status)), [contributions, search, status]);

  return <div className="space-y-6"><PageHeader eyebrow="Capital recebido" title="Aportes" description="Listagem demonstrativa de capital, vigência e disponibilidade para alocação." actions={<Button onClick={() => setModalOpen(true)}><Plus className="size-4" />Novo aporte</Button>} />
    <Card className="bg-card/75"><CardContent className="grid gap-3 p-4 md:grid-cols-[1fr_220px]"> <label className="relative"><Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" /><span className="sr-only">Buscar aportes</span><Input className="pl-9" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Código ou investidor demonstrativo…" /></label><label className="relative"><Filter className="absolute left-3 top-1/2 z-10 size-4 -translate-y-1/2 text-muted-foreground" /><span className="sr-only">Filtrar status</span><Select className="w-full pl-9" value={status} onChange={(event) => setStatus(event.target.value)}><option value="all">Todos os status</option><option value="available">Disponíveis</option><option value="partially_allocated">Parciais</option><option value="allocated">Alocados</option><option value="closed">Encerrados</option></Select></label></CardContent></Card>
    {state.status === "loading" && <LoadingState />}{state.status === "error" && <ErrorState message={state.error} onRetry={reload} />}{state.status === "success" && (filtered.length === 0 ? <EmptyState /> : <Card className="overflow-hidden bg-card/75"><Table><TableHeader><TableRow><TableHead>Aporte</TableHead><TableHead>Investidor</TableHead><TableHead>Status</TableHead><TableHead>Valor original</TableHead><TableHead>Disponível</TableHead><TableHead>Alocado</TableHead><TableHead>Taxa mensal</TableHead><TableHead>Vigência</TableHead><TableHead /></TableRow></TableHeader><TableBody>{filtered.map((item) => <TableRow key={item.id}><TableCell><div className="flex items-center gap-3"><div className="rounded-lg bg-primary/10 p-2"><WalletCards className="size-4 text-primary" /></div><AppLink to={`/aportes/${item.id}`} onNavigate={navigate} className="font-medium hover:text-primary">{item.code}</AppLink></div></TableCell><TableCell>{item.investorName}</TableCell><TableCell><StatusBadge status={item.status} /></TableCell><TableCell>{formatMoney(item.originalAmount)}</TableCell><TableCell className="font-medium text-emerald-400">{formatMoney(item.availableAmount)}</TableCell><TableCell>{formatMoney(item.allocatedAmount)}</TableCell><TableCell>{formatPercent(item.monthlyRate)}</TableCell><TableCell className="whitespace-nowrap">{formatDate(item.startDate)} – {formatDate(item.endDate)}</TableCell><TableCell><Button size="icon" variant="ghost" onClick={() => navigate(`/aportes/${item.id}`)} aria-label={`Ver ${item.code}`}><Eye className="size-4" /></Button></TableCell></TableRow>)}</TableBody></Table></Card>)}
    <Modal open={modalOpen} title="Novo aporte demonstrativo" description="O formulário simula a experiência e não grava no banco." onClose={() => setModalOpen(false)} footer={<><Button variant="outline" onClick={() => setModalOpen(false)}>Cancelar</Button><Button onClick={() => setModalOpen(false)}>Salvar demonstração</Button></>}><div className="grid gap-4 sm:grid-cols-2"><label className="space-y-2 sm:col-span-2"><span className="text-sm font-medium">Investidor</span><Select><option>Aurora Capital Demo</option><option>Horizonte Fundo Exemplo</option></Select></label><label className="space-y-2"><span className="text-sm font-medium">Valor original</span><Input inputMode="decimal" placeholder="R$ 100.000,00" /></label><label className="space-y-2"><span className="text-sm font-medium">Taxa mensal</span><Input inputMode="decimal" placeholder="1,45%" /></label><label className="space-y-2"><span className="text-sm font-medium">Início</span><Input type="date" /></label><label className="space-y-2"><span className="text-sm font-medium">Fim</span><Input type="date" /></label></div></Modal>
  </div>;
}
