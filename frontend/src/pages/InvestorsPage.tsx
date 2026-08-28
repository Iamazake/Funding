import { Eye, Pencil, Plus, Search, Users, WalletCards } from "lucide-react";
import { useCallback, useMemo, useState } from "react";

import { AppLink } from "@/components/app/AppLink";
import { EmptyState, ErrorState, LoadingState } from "@/components/common/DataStates";
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
import { useAsyncData } from "@/hooks/useAsyncData";
import { formatMoney } from "@/lib/formatters";
import { fundingApi } from "@/services/fundingApi";
import type { FundingInvestor, FundingInvestorInput } from "@/types/fundingApi";

export function InvestorsPage({ navigate }: { navigate: (path: string) => void }) {
  const loader = useCallback(async () => ({ investors: await fundingApi.listInvestors(), contributions: await fundingApi.listContributions() }), []);
  const { state, reload } = useAsyncData(loader);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [editing, setEditing] = useState<FundingInvestor>();
  const [formOpen, setFormOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const investors = useMemo(() => state.status === "success" ? state.data.investors : [], [state]);
  const contributions = state.status === "success" ? state.data.contributions : [];
  const filtered = useMemo(() => investors.filter((item) => {
    const term = search.trim().toLocaleLowerCase("pt-BR");
    return (!term || item.name.toLocaleLowerCase("pt-BR").includes(term) || item.code.toLowerCase().includes(term)) && (status === "all" || item.status === status);
  }), [investors, search, status]);
  const total = contributions.reduce((sum, item) => sum + BigInt(item.original_amount.replace(".", "")), 0n);
  const save = async (input: FundingInvestorInput) => {
    setSaving(true);
    try {
      if (editing) await fundingApi.updateInvestor(editing.id, input); else await fundingApi.createInvestor(input);
      setFeedback({ tone: "success", message: editing ? "Investidor atualizado." : "Investidor cadastrado." });
      setFormOpen(false); setEditing(undefined); reload();
    } catch (error) { setFeedback({ tone: "error", message: error instanceof Error ? error.message : "Falha ao salvar investidor." }); }
    finally { setSaving(false); }
  };
  return <div className="space-y-6">
    <PageHeader eyebrow="Cadastro" title="Investidores" description="Investidores reais cadastrados no módulo de Funding." actions={<Button onClick={() => { setEditing(undefined); setFormOpen(true); }}><Plus className="size-4" />Novo investidor</Button>} />
    <FeedbackBanner feedback={feedback} onClose={() => setFeedback(null)} />
    {state.status === "loading" && <LoadingState label="Carregando investidores…" />}
    {state.status === "error" && <ErrorState message={state.error} onRetry={reload} />}
    {state.status === "success" && <>
      <div className="grid gap-4 sm:grid-cols-3"><KpiCard compact icon={Users} label="Investidores ativos" value={String(investors.filter((item) => item.status === "ACTIVE").length)} helper={`${investors.length} cadastros no total`} /><KpiCard compact icon={WalletCards} label="Aportes cadastrados" value={String(contributions.length)} /><KpiCard compact icon={WalletCards} label="Capital original" value={formatMoney(`${total / 100n}.${(total % 100n).toString().padStart(2, "0")}`)} /></div>
      <Card className="bg-card/75"><CardContent className="grid gap-3 p-4 md:grid-cols-[1fr_200px]"><label className="relative"><Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" /><span className="sr-only">Buscar investidor</span><Input className="pl-9" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Buscar nome ou código…" /></label><Select value={status} onChange={(event) => setStatus(event.target.value)}><option value="all">Todos os status</option><option value="ACTIVE">Ativos</option><option value="INACTIVE">Inativos</option></Select></CardContent></Card>
      {investors.length === 0 ? <EmptyState title="Nenhum investidor cadastrado." description="Cadastre o primeiro investidor pela API real." /> : filtered.length === 0 ? <EmptyState title="Nenhum investidor encontrado." description="Ajuste os filtros da consulta." /> : <Card className="overflow-hidden bg-card/75"><Table><TableHeader><TableRow><TableHead>Código</TableHead><TableHead>Nome / documento</TableHead><TableHead>Contato</TableHead><TableHead>Status</TableHead><TableHead>Aportes</TableHead><TableHead className="text-right">Ações</TableHead></TableRow></TableHeader><TableBody>{filtered.map((item) => <TableRow key={item.id}><TableCell className="font-mono text-xs">{item.code}</TableCell><TableCell className="font-medium">{item.name}<p className="text-xs font-normal text-muted-foreground">{item.tax_id_masked ?? "Documento não informado"}</p></TableCell><TableCell>{item.phone ?? "Não informado"}</TableCell><TableCell><StatusBadge status={item.status} /></TableCell><TableCell>{contributions.filter((value) => value.investor_id === item.id).length}</TableCell><TableCell><div className="flex justify-end gap-2"><Button size="sm" variant="ghost" onClick={() => { setEditing(item); setFormOpen(true); }}><Pencil className="size-4" /><span className="sr-only">Editar</span></Button><AppLink to={`/cadastro/investidores/${item.id}`} onNavigate={navigate}><Button size="sm" variant="outline"><Eye className="size-4" />Ver</Button></AppLink></div></TableCell></TableRow>)}</TableBody></Table></Card>}
    </>}
    <InvestorFormModal open={formOpen} investor={editing} saving={saving} onClose={() => { setFormOpen(false); setEditing(undefined); }} onSave={save} />
  </div>;
}
