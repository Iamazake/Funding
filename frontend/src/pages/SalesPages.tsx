import { AlertTriangle, ArrowLeft, Banknote, CheckCircle2, Landmark, Layers3, Search, ShieldCheck, WalletCards } from "lucide-react";
import { useMemo, useState } from "react";

import { AppLink } from "@/components/app/AppLink";
import { EmptyState } from "@/components/common/DataStates";
import { FormField } from "@/components/common/FormField";
import { KpiCard } from "@/components/common/KpiCard";
import { PageHeader } from "@/components/common/PageHeader";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Tabs } from "@/components/common/Tabs";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatCentsAmount, formatDate, formatDateTime } from "@/lib/formatters";
import { cents, sumCents } from "@/repositories/fundingRepository";
import { useFundingState } from "@/services/fundingService";
import type { FundingContract } from "@/types/funding";

type State = ReturnType<typeof useFundingState>;

function allocationsFor(state: State, contractId: string) {
  return state.contractFundingAllocations.filter((item) => item.fundingContractId === contractId && !item.supersededAt);
}

function releaseFor(state: State, contractId: string) {
  return state.treasuryEntries.find((item) => item.fundingContractId === contractId && item.type === "LOAN_RELEASE" && item.status !== "ESTORNADO");
}

function validationFor(state: State, contract: FundingContract) {
  const release = releaseFor(state, contract.id);
  return contract.releaseValidationStatus ?? (release?.status === "CONFIRMADO" ? "VALID" : contract.fundingValidationStatus);
}

function referenceFor(state: State, contract: FundingContract) {
  return contract.releaseReference ?? releaseFor(state, contract.id)?.reference ?? "Não informada";
}

function accountFor(state: State, contract: FundingContract) {
  return contract.releaseBankAccount ?? releaseFor(state, contract.id)?.cashAccount ?? "Não informada";
}

function FundingParts({ state, contract }: { state: State; contract: FundingContract }) {
  const allocations = allocationsFor(state, contract.id);
  return <details className="min-w-52"><summary className="cursor-pointer font-medium">{allocations.length} {allocations.length === 1 ? "parte" : "partes"}</summary><div className="mt-2 space-y-2 rounded-lg border bg-popover p-3 text-xs shadow-xl">{allocations.map((allocation) => { const source = state.fundingSources.find((item) => item.id === allocation.fundingSourceId); const investor = state.investors.find((item) => item.id === allocation.investorId); return <div key={allocation.id}><strong>{source?.name ?? allocation.fundingSourceType}</strong><p className="text-muted-foreground">{investor?.name ?? (allocation.fundingSourceType === "REMO_OWN_CAPITAL" ? "Capital próprio REMO" : "Sem investidor")} · {formatCentsAmount(allocation.amount)}</p></div>; })}</div></details>;
}

export function SalesPage({ navigate }: { navigate: (path: string) => void }) {
  const state = useFundingState();
  const [search, setSearch] = useState(""); const [from, setFrom] = useState(""); const [to, setTo] = useState("");
  const [status, setStatus] = useState(""); const [validation, setValidation] = useState(""); const [bank, setBank] = useState("");
  const rows = useMemo(() => state.fundingContracts.filter((contract) => {
    const text = `${contract.contractCode} ${contract.maskedClientName} ${referenceFor(state, contract)}`.toLowerCase();
    return (!search || text.includes(search.toLowerCase())) && (!from || contract.releaseDate >= from) && (!to || contract.releaseDate <= to)
      && (!status || contract.status === status) && (!validation || validationFor(state, contract) === validation)
      && (!bank || accountFor(state, contract) === bank);
  }), [bank, from, search, state, status, to, validation]);
  const released = sumCents(rows.map((item) => item.releasedAmount));
  const ownCapital = sumCents(rows.flatMap((contract) => allocationsFor(state, contract.id).filter((item) => item.fundingSourceType === "REMO_OWN_CAPITAL").map((item) => item.amount)));
  const divergent = rows.filter((item) => state.fundingDivergences.some((divergence) => divergence.fundingContractId === item.id && ["OPEN", "IN_REVIEW"].includes(divergence.status))).length;
  const accounts = [...new Set(state.fundingContracts.map((item) => accountFor(state, item)))];
  return <div className="space-y-6">
    <PageHeader eyebrow="Vendas · saídas" title="Operações de liberação" description="Saídas de dinheiro ligadas à liberação e ao funding dos contratos demonstrativos." actions={<Button variant="outline" onClick={() => navigate("/vendas/validacao-bancaria")}><ShieldCheck className="size-4" />Validação bancária</Button>} />
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><KpiCard compact icon={WalletCards} label="Valor liberado" value={formatCentsAmount(released)} /><KpiCard compact icon={Layers3} label="Capital próprio REMO" value={formatCentsAmount(ownCapital)} /><KpiCard compact icon={CheckCircle2} label="Saídas validadas" value={String(rows.filter((item) => validationFor(state, item) === "VALID").length)} /><KpiCard compact icon={AlertTriangle} label="Com divergências" value={String(divergent)} /></div>
    <Card className="bg-card/75"><CardContent className="grid gap-3 p-4 sm:grid-cols-2 xl:grid-cols-6"><FormField label="Busca"><div className="relative"><Search className="absolute left-3 top-3 size-4 text-muted-foreground" /><Input className="pl-9" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Contrato, cliente ou referência" /></div></FormField><FormField label="Liberação de"><Input type="date" value={from} onChange={(event) => setFrom(event.target.value)} /></FormField><FormField label="Liberação até"><Input type="date" value={to} onChange={(event) => setTo(event.target.value)} /></FormField><FormField label="Status"><Select value={status} onChange={(event) => setStatus(event.target.value)}><option value="">Todos</option><option value="RELEASED">Liberado</option><option value="FUNDING_DIVERGENT">Funding divergente</option><option value="PENDING_FUNDING">Funding pendente</option><option value="CANCELLED">Cancelado</option></Select></FormField><FormField label="Validação da saída"><Select value={validation} onChange={(event) => setValidation(event.target.value)}><option value="">Todas</option><option value="VALID">Válida</option><option value="PENDING">Pendente</option><option value="DIVERGENT">Divergente</option><option value="CORRECTION_REQUIRED">Correção necessária</option></Select></FormField><FormField label="Banco/conta"><Select value={bank} onChange={(event) => setBank(event.target.value)}><option value="">Todos</option>{accounts.map((item) => <option key={item}>{item}</option>)}</Select></FormField></CardContent></Card>
    <Card className="overflow-hidden bg-card/75"><Table className="min-w-[1900px]"><TableHeader><TableRow><TableHead>Contrato / cliente</TableHead><TableHead>Venda / liberação</TableHead><TableHead>PMT</TableHead><TableHead>Taxa</TableHead><TableHead>Principal</TableHead><TableHead>Valor liberado</TableHead><TableHead>Valor financiado</TableHead><TableHead>Valor projetado</TableHead><TableHead>Referência</TableHead><TableHead>Operador de caixa</TableHead><TableHead>Banco/conta de saída</TableHead><TableHead>Partes / investidores</TableHead><TableHead>Capital REMO</TableHead><TableHead>Validação</TableHead><TableHead>Data validação</TableHead><TableHead>Status</TableHead><TableHead>Divergências</TableHead></TableRow></TableHeader><TableBody>{rows.map((contract) => { const own = sumCents(allocationsFor(state, contract.id).filter((item) => item.fundingSourceType === "REMO_OWN_CAPITAL").map((item) => item.amount)); const divergences = state.fundingDivergences.filter((item) => item.fundingContractId === contract.id && ["OPEN", "IN_REVIEW"].includes(item.status)); return <TableRow key={contract.id} className="cursor-pointer" onClick={() => navigate(`/vendas/${contract.id}`)}><TableCell><AppLink to={`/vendas/${contract.id}`} onNavigate={navigate} className="font-semibold hover:text-primary">{contract.contractCode}</AppLink><p className="text-xs text-muted-foreground">{contract.maskedClientName}</p></TableCell><TableCell>{formatDate(contract.releaseDate)}</TableCell><TableCell>{formatCentsAmount(contract.installmentAmount)}</TableCell><TableCell>{contract.interestRateBps} bps</TableCell><TableCell>{formatCentsAmount(contract.principalAmount)}</TableCell><TableCell>{formatCentsAmount(contract.releasedAmount)}</TableCell><TableCell>{formatCentsAmount(contract.financedAmount)}</TableCell><TableCell>{formatCentsAmount(contract.projectedAmount ?? contract.financedAmount)}</TableCell><TableCell>{referenceFor(state, contract)}</TableCell><TableCell>{contract.cashOperator ?? releaseFor(state, contract.id)?.owner ?? contract.responsibleUser}</TableCell><TableCell>{accountFor(state, contract)}</TableCell><TableCell onClick={(event) => event.stopPropagation()}><FundingParts state={state} contract={contract} /></TableCell><TableCell>{formatCentsAmount(own)}</TableCell><TableCell><StatusBadge status={validationFor(state, contract)} /></TableCell><TableCell>{formatDate(contract.releaseValidationDate)}</TableCell><TableCell><StatusBadge status={contract.status} /></TableCell><TableCell>{divergences.length ? <BadgeCount count={divergences.length} /> : "Nenhuma"}</TableCell></TableRow>; })}</TableBody></Table></Card>
  </div>;
}

const salesTabs = [
  { value: "summary", label: "Resumo" }, { value: "funding", label: "Composição do funding" },
  { value: "bank", label: "Validação bancária" }, { value: "movements", label: "Movimentos relacionados" },
  { value: "divergences", label: "Divergências" }, { value: "history", label: "Histórico" },
];

export function SalesDetailPage({ id, navigate }: { id: string; navigate: (path: string) => void }) {
  const state = useFundingState(); const contract = state.fundingContracts.find((item) => item.id === id); const [tab, setTab] = useState("summary");
  if (!contract) return <EmptyState title="Venda não encontrada" />;
  const allocations = allocationsFor(state, id); const movements = state.treasuryEntries.filter((item) => item.fundingContractId === id);
  const divergences = state.fundingDivergences.filter((item) => item.fundingContractId === id); const related = new Set([id, ...divergences.map((item) => item.id)]);
  const history = state.auditEvents.filter((item) => related.has(item.entityId)); const totalFunding = sumCents(allocations.map((item) => item.amount));
  const ownCapital = sumCents(allocations.filter((item) => item.fundingSourceType === "REMO_OWN_CAPITAL").map((item) => item.amount));
  return <div className="space-y-6">
    <AppLink to="/vendas" onNavigate={navigate} className="inline-flex items-center gap-2 text-sm text-muted-foreground"><ArrowLeft className="size-4" />Voltar para Vendas</AppLink>
    <PageHeader eyebrow="Vendas · saída" title={`${contract.contractCode} · ${contract.maskedClientName}`} description="Liberação do contrato e composição demonstrativa do funding, sem limite fixo de partes." actions={<StatusBadge status={contract.status} />} />
    <Tabs items={salesTabs} value={tab} onChange={setTab} />
    {tab === "summary" && <><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><KpiCard compact icon={Banknote} label="Valor liberado" value={formatCentsAmount(contract.releasedAmount)} /><KpiCard compact icon={Landmark} label="Principal" value={formatCentsAmount(contract.principalAmount)} /><KpiCard compact icon={Layers3} label="Funding informado" value={formatCentsAmount(totalFunding)} /><KpiCard compact icon={WalletCards} label="Capital REMO" value={formatCentsAmount(ownCapital)} /></div><InfoGrid rows={[["Data da venda/liberação", formatDate(contract.releaseDate)], ["Valor da parcela", formatCentsAmount(contract.installmentAmount)], ["Taxa de juros", `${contract.interestRateBps} bps`], ["Valor financiado", formatCentsAmount(contract.financedAmount)], ["Valor projetado", formatCentsAmount(contract.projectedAmount ?? contract.financedAmount)], ["Referência", referenceFor(state, contract)], ["Operador de caixa", contract.cashOperator ?? contract.responsibleUser], ["Banco/conta de saída", accountFor(state, contract)], ["Validação da saída", validationFor(state, contract)], ["Data da validação", formatDate(contract.releaseValidationDate)], ["Observação", contract.notes]]} /></>}
    {tab === "funding" && <SimpleTable headers={["Parte", "Fonte", "Investidor", "Aporte", "Valor do funding", "Saldo histórico", "Validação"]}>{allocations.map((item, index) => { const source = state.fundingSources.find((value) => value.id === item.fundingSourceId); const investor = state.investors.find((value) => value.id === item.investorId); const contribution = state.contributions.find((value) => value.id === item.contributionId); return <TableRow key={item.id}><TableCell>{index + 1}</TableCell><TableCell>{source?.name ?? item.fundingSourceType}</TableCell><TableCell>{investor?.name ?? (item.fundingSourceType === "REMO_OWN_CAPITAL" ? "Capital próprio REMO" : "—")}</TableCell><TableCell>{contribution?.code ?? "—"}</TableCell><TableCell>{formatCentsAmount(item.amount)}</TableCell><TableCell>{formatCentsAmount(item.historicalAvailableBalance)}</TableCell><TableCell><StatusBadge status={item.validationStatus} /></TableCell></TableRow>; })}</SimpleTable>}
    {tab === "bank" && <><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><KpiCard compact icon={Banknote} label="Saída esperada" value={formatCentsAmount(contract.releasedAmount)} /><KpiCard compact icon={CheckCircle2} label="Saída registrada" value={formatCentsAmount(releaseFor(state, id)?.amount ?? "0")} /><KpiCard compact icon={AlertTriangle} label="Diferença" value={formatCentsAmount((cents(contract.releasedAmount) - cents(releaseFor(state, id)?.amount ?? "0")).toString())} /><KpiCard compact icon={ShieldCheck} label="Validação" value={validationFor(state, contract)} /></div><InfoGrid rows={[["Banco/conta", accountFor(state, contract)], ["Referência bancária", referenceFor(state, contract)], ["Operador de caixa", contract.cashOperator ?? contract.responsibleUser], ["Data da validação", formatDate(contract.releaseValidationDate)]]} /></>}
    {tab === "movements" && <SimpleTable headers={["Data", "Tipo", "Natureza", "Valor", "Conta", "Referência", "Responsável", "Status"]}>{movements.map((item) => <TableRow key={item.id}><TableCell>{formatDate(item.date)}</TableCell><TableCell>{item.type.replaceAll("_", " ")}</TableCell><TableCell><StatusBadge status={item.direction} /></TableCell><TableCell>{formatCentsAmount(item.amount)}</TableCell><TableCell>{item.cashAccount}</TableCell><TableCell>{item.reference}</TableCell><TableCell>{item.owner}</TableCell><TableCell><StatusBadge status={item.status} /></TableCell></TableRow>)}</SimpleTable>}
    {tab === "divergences" && <FundingDivergenceTable state={state} rows={divergences} navigate={navigate} />}
    {tab === "history" && <Card className="bg-card/75"><CardContent className="space-y-4 p-6">{history.map((item) => <div key={item.id}><p className="text-sm">{item.description}</p><p className="text-xs text-muted-foreground">{formatDateTime(item.date)} · {item.demoUser}</p></div>)}</CardContent></Card>}
  </div>;
}

export function SalesDivergencesPage({ navigate }: { navigate: (path: string) => void }) {
  const state = useFundingState();
  return <div className="space-y-6"><PageHeader eyebrow="Vendas · saídas" title="Divergências" description="Diferenças de funding e liberação que exigem revisão operacional." /><FundingDivergenceTable state={state} rows={state.fundingDivergences} navigate={navigate} /></div>;
}

export function SalesBankValidationPage({ navigate }: { navigate: (path: string) => void }) {
  const state = useFundingState(); const [status, setStatus] = useState("");
  const rows = state.fundingContracts.filter((item) => !status || validationFor(state, item) === status);
  return <div className="space-y-6"><PageHeader eyebrow="Vendas · saídas" title="Validação bancária" description="Conferência demonstrativa das saídas de caixa referentes às liberações." /><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><KpiCard compact icon={Banknote} label="Saídas para conferir" value={String(rows.length)} /><KpiCard compact icon={CheckCircle2} label="Validadas" value={String(rows.filter((item) => validationFor(state, item) === "VALID").length)} /><KpiCard compact icon={AlertTriangle} label="Divergentes" value={String(rows.filter((item) => validationFor(state, item) === "DIVERGENT").length)} /><KpiCard compact icon={WalletCards} label="Total liberado" value={formatCentsAmount(sumCents(rows.map((item) => item.releasedAmount)))} /></div><Card className="bg-card/75"><CardContent className="max-w-sm p-4"><FormField label="Status da validação"><Select value={status} onChange={(event) => setStatus(event.target.value)}><option value="">Todos</option><option value="VALID">Válida</option><option value="PENDING">Pendente</option><option value="DIVERGENT">Divergente</option><option value="CORRECTION_REQUIRED">Correção necessária</option></Select></FormField></CardContent></Card><SimpleTable headers={["Contrato", "Data da saída", "Valor liberado", "Valor registrado", "Diferença", "Banco/conta", "Referência", "Operador", "Validação", "Data da validação"]}>{rows.map((contract) => { const release = releaseFor(state, contract.id); return <TableRow key={contract.id} className="cursor-pointer" onClick={() => navigate(`/vendas/${contract.id}`)}><TableCell>{contract.contractCode}<p className="text-xs text-muted-foreground">{contract.maskedClientName}</p></TableCell><TableCell>{formatDate(contract.releaseDate)}</TableCell><TableCell>{formatCentsAmount(contract.releasedAmount)}</TableCell><TableCell>{formatCentsAmount(release?.amount ?? "0")}</TableCell><TableCell>{formatCentsAmount((cents(contract.releasedAmount) - cents(release?.amount ?? "0")).toString())}</TableCell><TableCell>{accountFor(state, contract)}</TableCell><TableCell>{referenceFor(state, contract)}</TableCell><TableCell>{contract.cashOperator ?? release?.owner ?? contract.responsibleUser}</TableCell><TableCell><StatusBadge status={validationFor(state, contract)} /></TableCell><TableCell>{formatDate(contract.releaseValidationDate)}</TableCell></TableRow>; })}</SimpleTable></div>;
}

function FundingDivergenceTable({ state, rows, navigate }: { state: State; rows: State["fundingDivergences"]; navigate: (path: string) => void }) {
  return <SimpleTable headers={["Contrato", "Tipo", "Esperado", "Identificado", "Diferença", "Situação", "Histórico"]}>{rows.map((item) => { const contract = state.fundingContracts.find((value) => value.id === item.fundingContractId); return <TableRow key={item.id} className="cursor-pointer" onClick={() => navigate(`/vendas/${item.fundingContractId}`)}><TableCell>{contract?.contractCode ?? item.fundingContractId}<p className="text-xs text-muted-foreground">{contract?.maskedClientName}</p></TableCell><TableCell>{item.type.replaceAll("_", " ")}</TableCell><TableCell>{formatCentsAmount(item.expectedAmount)}</TableCell><TableCell>{formatCentsAmount(item.identifiedAmount)}</TableCell><TableCell>{formatCentsAmount(item.differenceAmount)}</TableCell><TableCell><StatusBadge status={item.status} /></TableCell><TableCell>{item.resolutionNotes ?? item.description}</TableCell></TableRow>; })}</SimpleTable>;
}

function BadgeCount({ count }: { count: number }) { return <span className="inline-flex rounded-full bg-rose-500/15 px-2 py-1 text-xs font-medium text-rose-400">{count} aberta{count === 1 ? "" : "s"}</span>; }
function InfoGrid({ rows }: { rows: [string, string][] }) { return <Card className="bg-card/75"><CardContent className="grid gap-4 p-6 sm:grid-cols-2 xl:grid-cols-3">{rows.map(([label, value]) => <div key={label}><p className="text-xs uppercase tracking-wider text-muted-foreground">{label}</p><p className="mt-1 text-sm font-medium">{value}</p></div>)}</CardContent></Card>; }
function SimpleTable({ headers, children }: { headers: string[]; children: React.ReactNode }) { return <Card className="overflow-hidden bg-card/75"><Table><TableHeader><TableRow>{headers.map((header) => <TableHead key={header}>{header}</TableHead>)}</TableRow></TableHeader><TableBody>{children}</TableBody></Table></Card>; }
