import { Eye, Pencil, Plus, Search, ShieldCheck, Users, WalletCards } from "lucide-react";
import { useMemo, useState } from "react";

import { AppLink } from "@/components/app/AppLink";
import { EmptyState } from "@/components/common/DataStates";
import { FeedbackBanner, type Feedback } from "@/components/common/FeedbackBanner";
import { KpiCard } from "@/components/common/KpiCard";
import { PageHeader } from "@/components/common/PageHeader";
import { StatusBadge } from "@/components/common/StatusBadge";
import { InvestorFormModal } from "@/components/funding/InvestorFormModal";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatCentsAmount, formatDate } from "@/lib/formatters";
import { sumCents } from "@/repositories/fundingRepository";
import { fundingRepository, useFundingState } from "@/services/fundingService";
import type { Investor, InvestorInput } from "@/types/funding";

export function InvestorsPage({ navigate }: { navigate: (path: string) => void }) {
  const state = useFundingState();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [type, setType] = useState("all");
  const [risk, setRisk] = useState("all");
  const [editing, setEditing] = useState<Investor | undefined>();
  const [formOpen, setFormOpen] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const filtered = useMemo(() => state.investors.filter((item) => {
    const term = search.toLocaleLowerCase("pt-BR");
    return (item.name.toLocaleLowerCase("pt-BR").includes(term) || item.code.toLowerCase().includes(term))
      && (status === "all" || item.status === status) && (type === "all" || item.personType === type) && (risk === "all" || item.riskGrade === risk);
  }), [state.investors, search, status, type, risk]);
  const active = state.investors.filter((item) => item.status === "ATIVO").length;
  const signed = state.investors.filter((item) => item.contractSigned).length;
  const totalCapital = sumCents(state.contributions.filter((item) => item.status !== "CANCELADO").map((item) => item.originalAmount));
  const available = sumCents(state.contributions.filter((item) => item.status !== "CANCELADO").map((item) => item.availableBalance));
  const save = (input: InvestorInput) => {
    if (editing) fundingRepository.updateInvestor(editing.id, input); else fundingRepository.createInvestor(input);
    setFeedback({ tone: "success", message: editing ? "Investidor atualizado e persistido localmente." : "Investidor criado e persistido localmente." });
    setFormOpen(false); setEditing(undefined);
  };
  return <div className="space-y-6">
    <PageHeader eyebrow="Cadastro" title="Investidores" description="Situação cadastral, contratos, risco e posição consolidada dos investidores fictícios." actions={<Button onClick={() => { setEditing(undefined); setFormOpen(true); }}><Plus className="size-4" />Novo investidor</Button>} />
    <FeedbackBanner feedback={feedback} onClose={() => setFeedback(null)} />
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><KpiCard compact icon={Users} label="Investidores ativos" value={String(active)} helper={`${state.investors.length} cadastros no total`} /><KpiCard compact icon={ShieldCheck} label="Contratos assinados" value={String(signed)} /><KpiCard compact icon={WalletCards} label="Capital principal" value={formatCentsAmount(totalCapital)} /><KpiCard compact icon={WalletCards} label="Saldo disponível" value={formatCentsAmount(available)} /></div>
    <Card className="bg-card/75"><CardContent className="grid gap-3 p-4 lg:grid-cols-[1fr_180px_180px_180px]"><label className="relative"><Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" /><span className="sr-only">Buscar investidor</span><Input className="pl-9" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Buscar nome ou código…" /></label><Select value={status} onChange={(event) => setStatus(event.target.value)}><option value="all">Todos os status</option><option value="ATIVO">Ativos</option><option value="PENDENTE">Pendentes</option><option value="INATIVO">Inativos</option><option value="ENCERRADO">Encerrados</option></Select><Select value={type} onChange={(event) => setType(event.target.value)}><option value="all">PF e PJ</option><option value="PF">Pessoa física</option><option value="PJ">Pessoa jurídica</option></Select><Select value={risk} onChange={(event) => setRisk(event.target.value)}><option value="all">Todos os riscos</option><option value="BAIXO">Baixo</option><option value="MEDIO">Médio</option><option value="ALTO">Alto</option></Select></CardContent></Card>
    {filtered.length === 0 ? <EmptyState /> : <Card className="overflow-hidden bg-card/75"><Table><TableHeader><TableRow><TableHead>Investidor</TableHead><TableHead>Situação</TableHead><TableHead>Tipo / risco</TableHead><TableHead>Contrato</TableHead><TableHead>Dia de pagamento</TableHead><TableHead>Aportes</TableHead><TableHead>Capital</TableHead><TableHead className="text-right">Ações</TableHead></TableRow></TableHeader><TableBody>{filtered.map((investor) => { const contributions = state.contributions.filter((item) => item.investorId === investor.id && item.status !== "CANCELADO"); return <TableRow key={investor.id}><TableCell><div><AppLink to={`/cadastro/investidores/${investor.id}`} onNavigate={navigate} className="font-medium hover:text-primary">{investor.name}</AppLink><p className="text-xs text-muted-foreground">{investor.code} · {investor.maskedDocument}</p></div></TableCell><TableCell><StatusBadge status={investor.status} /></TableCell><TableCell>{investor.personType}<div className="mt-1"><StatusBadge status={investor.riskGrade} /></div></TableCell><TableCell>{investor.contractSigned ? "Assinado" : "Pendente"}<p className="text-xs text-muted-foreground">{formatDate(investor.signedAt)}</p></TableCell><TableCell>Dia {investor.paymentDay}</TableCell><TableCell>{contributions.length}</TableCell><TableCell className="font-medium">{formatCentsAmount(sumCents(contributions.map((item) => item.originalAmount)))}</TableCell><TableCell><div className="flex justify-end gap-1"><Button size="icon" variant="ghost" onClick={() => navigate(`/cadastro/investidores/${investor.id}`)} aria-label={`Ver ${investor.name}`}><Eye className="size-4" /></Button><Button size="icon" variant="ghost" onClick={() => { setEditing(investor); setFormOpen(true); }} aria-label={`Editar ${investor.name}`}><Pencil className="size-4" /></Button></div></TableCell></TableRow>; })}</TableBody></Table></Card>}
    <InvestorFormModal open={formOpen} investor={editing} onClose={() => { setFormOpen(false); setEditing(undefined); }} onSave={save} />
  </div>;
}
