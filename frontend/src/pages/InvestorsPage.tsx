import { ArrowUpDown, Eye, Pencil, Plus, Search, Users } from "lucide-react";
import { useCallback, useMemo, useState } from "react";

import { AppLink } from "@/components/app/AppLink";
import { DemoStateSwitcher, type DemoViewState } from "@/components/common/DemoStateSwitcher";
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
import { formatDate, formatMoney } from "@/lib/formatters";
import { fundingService } from "@/services/fundingService";
import type { Investor } from "@/types/funding";

const typeLabels = { individual: "Pessoa física", company: "Empresa", fund: "Fundo" } as const;

interface InvestorsPageProps { navigate: (path: string) => void; }

export function InvestorsPage({ navigate }: InvestorsPageProps) {
  const loader = useCallback(() => fundingService.investors.listInvestors(), []);
  const { state, reload } = useAsyncData(loader);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [type, setType] = useState("all");
  const [sortAsc, setSortAsc] = useState(true);
  const [page, setPage] = useState(1);
  const [viewState, setViewState] = useState<DemoViewState>("ready");
  const [modal, setModal] = useState<{ mode: "create" | "edit"; investor?: Investor } | null>(null);

  const investors = useMemo(() => state.status === "success" ? state.data : [], [state]);
  const filtered = useMemo(() => investors.filter((investor) => {
    const matchesSearch = investor.name.toLocaleLowerCase("pt-BR").includes(search.toLocaleLowerCase("pt-BR"));
    return matchesSearch && (status === "all" || investor.status === status) && (type === "all" || investor.type === type);
  }).sort((left, right) => (sortAsc ? 1 : -1) * left.name.localeCompare(right.name, "pt-BR")), [investors, search, status, type, sortAsc]);
  const pageSize = 4;
  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
  const visible = filtered.slice((page - 1) * pageSize, page * pageSize);

  const contentState = viewState !== "ready" ? viewState : state.status;
  return <div className="space-y-6">
    <PageHeader eyebrow="Relacionamento" title="Investidores" description="Gestão visual da posição dos investidores fictícios e seus próximos eventos." actions={<Button onClick={() => setModal({ mode: "create" })}><Plus className="size-4" />Novo investidor</Button>} />
    <Card className="bg-card/75"><CardContent className="p-4"><div className="grid gap-3 lg:grid-cols-[minmax(220px,1fr)_180px_180px_auto]">
      <label className="relative"><Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" /><span className="sr-only">Buscar investidor</span><Input className="pl-9" value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Buscar por nome demonstrativo…" /></label>
      <Select value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }} aria-label="Filtrar por status"><option value="all">Todos os status</option><option value="active">Ativos</option><option value="pending">Pendentes</option><option value="inactive">Inativos</option></Select>
      <Select value={type} onChange={(event) => { setType(event.target.value); setPage(1); }} aria-label="Filtrar por tipo"><option value="all">Todos os tipos</option><option value="individual">Pessoa física</option><option value="company">Empresa</option><option value="fund">Fundo</option></Select>
      <Button variant="outline" onClick={() => setSortAsc((value) => !value)}><ArrowUpDown className="size-4" />{sortAsc ? "A–Z" : "Z–A"}</Button>
    </div><div className="mt-3 flex justify-end"><DemoStateSwitcher value={viewState} onChange={setViewState} /></div></CardContent></Card>
    {contentState === "loading" && <LoadingState />}{contentState === "error" && <ErrorState onRetry={() => { setViewState("ready"); reload(); }} />}{contentState === "empty" && <EmptyState title="Nenhum investidor demonstrativo" action={<Button onClick={() => setModal({ mode: "create" })}>Criar demonstração</Button>} />}
    {contentState === "success" && (visible.length === 0 ? <EmptyState description="Nenhum investidor corresponde aos filtros atuais." /> : <Card className="overflow-hidden bg-card/75"><Table><TableHeader><TableRow><TableHead>Investidor</TableHead><TableHead>Status</TableHead><TableHead>Capital aportado</TableHead><TableHead>Saldo livre</TableHead><TableHead>Saldo alocado</TableHead><TableHead>Remuneração</TableHead><TableHead>Próximo pagamento</TableHead><TableHead className="text-right">Ações</TableHead></TableRow></TableHeader><TableBody>{visible.map((investor) => <TableRow key={investor.id}><TableCell><div className="flex items-center gap-3"><div className="flex size-9 items-center justify-center rounded-full bg-primary/10 text-primary"><Users className="size-4" /></div><div><AppLink to={`/investidores/${investor.id}`} onNavigate={navigate} className="font-medium hover:text-primary">{investor.name}</AppLink><p className="mt-0.5 text-xs text-muted-foreground">{typeLabels[investor.type]} · {investor.maskedDocument}</p></div></div></TableCell><TableCell><StatusBadge status={investor.status} /></TableCell><TableCell className="font-medium">{formatMoney(investor.contributedCapital)}</TableCell><TableCell>{formatMoney(investor.availableBalance)}</TableCell><TableCell>{formatMoney(investor.allocatedBalance)}</TableCell><TableCell>{formatMoney(investor.accumulatedReturn)}</TableCell><TableCell><p>{formatDate(investor.nextPaymentDate)}</p><p className="text-xs text-muted-foreground">{formatMoney(investor.nextPaymentAmount)}</p></TableCell><TableCell><div className="flex justify-end gap-1"><Button size="icon" variant="ghost" onClick={() => navigate(`/investidores/${investor.id}`)} aria-label={`Ver ${investor.name}`}><Eye className="size-4" /></Button><Button size="icon" variant="ghost" onClick={() => setModal({ mode: "edit", investor })} aria-label={`Editar ${investor.name}`}><Pencil className="size-4" /></Button></div></TableCell></TableRow>)}</TableBody></Table>
      <div className="flex items-center justify-between border-t border-border p-4 text-sm text-muted-foreground"><span>{filtered.length} investidores demonstrativos</span><div className="flex items-center gap-2"><Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Anterior</Button><span>Página {page} de {pageCount}</span><Button size="sm" variant="outline" disabled={page >= pageCount} onClick={() => setPage((value) => value + 1)}>Próxima</Button></div></div>
    </Card>)}
    <InvestorModal modal={modal} onClose={() => setModal(null)} />
  </div>;
}

function InvestorModal({ modal, onClose }: { modal: { mode: "create" | "edit"; investor?: Investor } | null; onClose: () => void }) {
  return <Modal open={modal !== null} title={modal?.mode === "edit" ? "Editar investidor demonstrativo" : "Novo investidor demonstrativo"} description="O formulário não persiste dados e não utiliza documentos reais." onClose={onClose} footer={<><Button variant="outline" onClick={onClose}>Cancelar</Button><Button onClick={onClose}>Salvar demonstração</Button></>}>
    <div className="grid gap-4 sm:grid-cols-2"><label className="space-y-2 sm:col-span-2"><span className="text-sm font-medium">Nome demonstrativo</span><Input defaultValue={modal?.investor?.name} placeholder="Ex.: Investidor Delta Demo" /></label><label className="space-y-2"><span className="text-sm font-medium">Tipo</span><Select defaultValue={modal?.investor?.type ?? "individual"}><option value="individual">Pessoa física</option><option value="company">Empresa</option><option value="fund">Fundo</option></Select></label><label className="space-y-2"><span className="text-sm font-medium">Status</span><Select defaultValue={modal?.investor?.status ?? "pending"}><option value="active">Ativo</option><option value="pending">Pendente</option><option value="inactive">Inativo</option></Select></label><label className="space-y-2 sm:col-span-2"><span className="text-sm font-medium">E-mail fictício</span><Input type="email" defaultValue={modal?.investor?.email} placeholder="investidor@exemplo.demo" /></label></div>
  </Modal>;
}
