import { AlertTriangle, ArrowLeft, Landmark, Layers3, Search } from "lucide-react";
import { useState } from "react";

import { AppLink } from "@/components/app/AppLink";
import { EmptyState } from "@/components/common/DataStates";
import { FeedbackBanner, type Feedback } from "@/components/common/FeedbackBanner";
import { KpiCard } from "@/components/common/KpiCard";
import { PageHeader } from "@/components/common/PageHeader";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Tabs } from "@/components/common/Tabs";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatCentsAmount, formatDate, formatDateTime } from "@/lib/formatters";
import { cents, sumCents } from "@/repositories/fundingRepository";
import { fundingRepository, useFundingState } from "@/services/fundingService";

function activeAllocations(state: ReturnType<typeof useFundingState>, contractId: string) {
  return state.contractFundingAllocations.filter((item) => item.fundingContractId === contractId && !item.supersededAt);
}

function coverage(total: string, expected: string): string {
  if (cents(expected) === 0n) return "0,00%";
  const bps = cents(total) * 10_000n / cents(expected);
  return `${bps / 100n},${(bps % 100n).toString().padStart(2, "0")}%`;
}

export function ContractsPage({ navigate }: { navigate: (path: string) => void }) {
  const state = useFundingState();
  const [search, setSearch] = useState("");
  const rows = state.fundingContracts.filter((item) => `${item.contractCode} ${item.maskedClientName}`.toLowerCase().includes(search.toLowerCase()));
  return <div className="space-y-6">
    <PageHeader eyebrow="Contratos" title="Contratos e operações de funding" description="Originação, liberação e composição do funding permanecem separadas das entradas bancárias." />
    <Card className="bg-card/75"><CardContent className="p-4"><label className="relative block"><Search className="absolute left-3 top-3 size-4 text-muted-foreground" /><Input className="pl-9" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Contrato ou cliente mascarado…" /></label></CardContent></Card>
    <Card className="overflow-hidden bg-card/75"><Table><TableHeader><TableRow><TableHead>Contrato / cliente</TableHead><TableHead>Operação</TableHead><TableHead>Liberação</TableHead><TableHead>Principal</TableHead><TableHead>Financiado</TableHead><TableHead>Liberado</TableHead><TableHead>PMT</TableHead><TableHead>Funding</TableHead><TableHead>Status</TableHead></TableRow></TableHeader><TableBody>{rows.map((contract) => { const allocations = activeAllocations(state, contract.id); const total = sumCents(allocations.map((item) => item.amount)); return <TableRow key={contract.id}><TableCell><AppLink to={`/contratos/${contract.id}`} onNavigate={navigate} className="font-medium hover:text-primary">{contract.contractCode}</AppLink><p className="text-xs text-muted-foreground">{contract.maskedClientName}</p></TableCell><TableCell>{formatDate(contract.operationDate)}</TableCell><TableCell>{formatDate(contract.releaseDate)}</TableCell><TableCell>{formatCentsAmount(contract.principalAmount)}</TableCell><TableCell>{formatCentsAmount(contract.financedAmount)}</TableCell><TableCell>{formatCentsAmount(contract.releasedAmount)}</TableCell><TableCell>{formatCentsAmount(contract.installmentAmount)}</TableCell><TableCell>{formatCentsAmount(total)}<p className="text-xs text-muted-foreground">{coverage(total, contract.releasedAmount)}</p></TableCell><TableCell><StatusBadge status={contract.status} /></TableCell></TableRow>; })}</TableBody></Table></Card>
  </div>;
}

const tabs = [
  { value: "summary", label: "Resumo" }, { value: "funding", label: "Composição do funding" },
  { value: "allocations", label: "Alocações" }, { value: "revenue", label: "Receita" }, { value: "exits", label: "Saídas" },
  { value: "divergences", label: "Divergências" }, { value: "history", label: "Histórico" },
];

export function ContractDetailPage({ id, navigate, fundingOnly = false }: { id: string; navigate: (path: string) => void; fundingOnly?: boolean }) {
  const state = useFundingState();
  const contract = state.fundingContracts.find((item) => item.id === id);
  const [tab, setTab] = useState(fundingOnly ? "funding" : "summary");
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  if (!contract) return <EmptyState title="Contrato não encontrado" />;
  const allocations = activeAllocations(state, id);
  const allAllocations = state.contractFundingAllocations.filter((item) => item.fundingContractId === id);
  const total = sumCents(allocations.map((item) => item.amount));
  const remo = sumCents(allocations.filter((item) => item.fundingSourceType === "REMO_OWN_CAPITAL").map((item) => item.amount));
  const unidentified = sumCents(allocations.filter((item) => item.fundingSourceType === "UNIDENTIFIED_SOURCE").map((item) => item.amount));
  const difference = (cents(contract.releasedAmount) - cents(total)).toString();
  const divergences = state.fundingDivergences.filter((item) => item.fundingContractId === id);
  const exits = state.treasuryEntries.filter((item) => item.fundingContractId === id && item.direction === "SAIDA");
  const receipts = state.treasuryIncomingReceipts.filter((item) => item.fundingContractId === id);
  const history = state.auditEvents.filter((item) => item.entityId === id || divergences.some((value) => value.id === item.entityId));
  const completeWithRemo = () => {
    const identified = allocations.filter((item) => item.fundingSourceType !== "UNIDENTIFIED_SOURCE");
    const required = cents(contract.releasedAmount) - cents(sumCents(identified.map((item) => item.amount)));
    const source = state.fundingSources.find((item) => item.type === "REMO_OWN_CAPITAL");
    if (!source || required <= 0n) return;
    fundingRepository.reviseContractFunding(id, [
      ...identified.map(({ fundingSourceType, contributionId, investorId, fundingSourceId, amount, allocationDate, notes }) => ({ fundingSourceType, contributionId, investorId, fundingSourceId, amount, allocationDate, notes })),
      { fundingSourceType: "REMO_OWN_CAPITAL", fundingSourceId: source.id, amount: required.toString(), allocationDate: contract.operationDate, notes: "Capital REMO incluído na correção." },
    ], "Operador Demo");
    setFeedback({ tone: "success", message: "Composição corrigida; a versão anterior permanece no histórico." });
  };
  return <div className="space-y-6">
    <AppLink to="/contratos" onNavigate={navigate} className="inline-flex items-center gap-2 text-sm text-muted-foreground"><ArrowLeft className="size-4" />Voltar</AppLink>
    <PageHeader eyebrow={contract.contractCode} title={contract.maskedClientName} description="Contrato e composição de funding; entradas de PMT são tratadas separadamente na Tesouraria." actions={<StatusBadge status={contract.status} />} />
    <FeedbackBanner feedback={feedback} onClose={() => setFeedback(null)} />
    <Tabs items={tabs} value={tab} onChange={setTab} />
    {tab === "summary" && <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><KpiCard compact icon={Landmark} label="Valor liberado" value={formatCentsAmount(contract.releasedAmount)} /><KpiCard compact icon={Layers3} label="Funding informado" value={formatCentsAmount(total)} /><KpiCard compact icon={Landmark} label="Capital REMO" value={formatCentsAmount(remo)} /><KpiCard compact icon={AlertTriangle} label="Diferença" value={formatCentsAmount(difference)} helper={`${coverage(total, contract.releasedAmount)} coberto`} /></div>}
    {tab === "funding" && <Card className="overflow-hidden bg-card/75"><CardHeader><CardTitle className="flex justify-between text-base"><span>Composição atual · não identificado {formatCentsAmount(unidentified)}</span>{cents(difference) > 0n && <Button size="sm" onClick={completeWithRemo}>Completar com capital REMO</Button>}</CardTitle></CardHeader><AllocationTable rows={allocations} /></Card>}
    {tab === "allocations" && <Card className="overflow-hidden bg-card/75"><CardHeader><CardTitle className="text-base">Versões das alocações</CardTitle></CardHeader><AllocationTable rows={allAllocations} showVersion /></Card>}
    {tab === "revenue" && <SimpleTable headers={["Recebimento", "Parcela", "Vencimento", "Pago", "Banco", "Acesso"]}>{receipts.map((item) => <TableRow key={item.id}><TableCell>{item.id}</TableCell><TableCell>{item.installmentNumber}/{item.totalInstallments}</TableCell><TableCell>{formatDate(item.dueDate)}</TableCell><TableCell>{formatCentsAmount(item.paidAmountFromOperationalSource)}</TableCell><TableCell><StatusBadge status={item.bankValidationStatus} /></TableCell><TableCell><AppLink to={`/receita/${item.id}`} onNavigate={navigate} className="text-primary">Abrir Receita</AppLink></TableCell></TableRow>)}</SimpleTable>}
    {tab === "exits" && <SimpleTable headers={["Data", "Tipo", "Valor", "Conta", "Referência", "Status"]}>{exits.map((item) => <TableRow key={item.id}><TableCell>{formatDate(item.date)}</TableCell><TableCell>{item.type.replaceAll("_", " ")}</TableCell><TableCell>{formatCentsAmount(item.amount)}</TableCell><TableCell>{item.cashAccount}</TableCell><TableCell>{item.reference}</TableCell><TableCell><StatusBadge status={item.status} /></TableCell></TableRow>)}</SimpleTable>}
    {tab === "divergences" && <FundingDivergenceTable rows={divergences} />}
    {tab === "history" && <Card className="bg-card/75"><CardContent className="space-y-4 p-6">{history.map((item) => <div key={item.id}><p className="text-sm">{item.description}</p><p className="text-xs text-muted-foreground">{formatDateTime(item.date)} · {item.demoUser}</p></div>)}</CardContent></Card>}
  </div>;
}

function AllocationTable({ rows, showVersion = false }: { rows: ReturnType<typeof useFundingState>["contractFundingAllocations"]; showVersion?: boolean }) {
  const state = useFundingState();
  return <Table><TableHeader><TableRow><TableHead>Fonte</TableHead><TableHead>Valor</TableHead><TableHead>Saldo histórico</TableHead><TableHead>Validação</TableHead>{showVersion && <><TableHead>Válida desde</TableHead><TableHead>Válida até</TableHead></>}</TableRow></TableHeader><TableBody>{rows.map((item) => <TableRow key={item.id}><TableCell>{state.fundingSources.find((source) => source.id === item.fundingSourceId)?.name}<p className="text-xs text-muted-foreground">{item.fundingSourceType.replaceAll("_", " ")}</p></TableCell><TableCell>{formatCentsAmount(item.amount)}</TableCell><TableCell>{formatCentsAmount(item.historicalAvailableBalance)}</TableCell><TableCell><StatusBadge status={item.validationStatus} /></TableCell>{showVersion && <><TableCell>{formatDate(item.validFrom)}</TableCell><TableCell>{formatDate(item.validUntil)}</TableCell></>}</TableRow>)}</TableBody></Table>;
}

function FundingDivergenceTable({ rows }: { rows: ReturnType<typeof useFundingState>["fundingDivergences"] }) {
  return <SimpleTable headers={["Tipo", "Esperado", "Identificado", "Diferença", "Data", "Situação", "Histórico"]}>{rows.map((item) => <TableRow key={item.id}><TableCell>{item.type.replaceAll("_", " ")}</TableCell><TableCell>{formatCentsAmount(item.expectedAmount)}</TableCell><TableCell>{formatCentsAmount(item.identifiedAmount)}</TableCell><TableCell>{formatCentsAmount(item.differenceAmount)}</TableCell><TableCell>{formatDate(item.createdAt)}</TableCell><TableCell><StatusBadge status={item.status} /></TableCell><TableCell>{item.resolutionNotes ?? item.description}</TableCell></TableRow>)}</SimpleTable>;
}

export function ContractCompositionPage({ navigate }: { navigate: (path: string) => void }) {
  const state = useFundingState();
  return <div className="space-y-6"><PageHeader eyebrow="Contratos" title="Composição do funding" description="Visão consolidada da composição atual por contrato." />{state.fundingContracts.map((contract) => <Card key={contract.id} className="bg-card/75"><CardHeader><CardTitle className="flex items-center justify-between text-base"><span>{contract.contractCode} · {contract.maskedClientName}</span><Button size="sm" variant="outline" onClick={() => navigate(`/contratos/${contract.id}/funding`)}>Abrir composição</Button></CardTitle></CardHeader><AllocationTable rows={activeAllocations(state, contract.id)} /></Card>)}</div>;
}

export function ContractAllocationsPage() {
  const state = useFundingState();
  return <div className="space-y-6"><PageHeader eyebrow="Contratos" title="Alocações" description="Alocações atuais e versões históricas, sem limite fixo de fontes." /><Card className="overflow-hidden bg-card/75"><AllocationTable rows={state.contractFundingAllocations} showVersion /></Card></div>;
}

export function ContractDivergencesPage() {
  const state = useFundingState();
  return <div className="space-y-6"><PageHeader eyebrow="Contratos" title="Divergências de funding" description="Diferenças de composição separadas das divergências bancárias de entradas." /><FundingDivergenceTable rows={state.fundingDivergences} /></div>;
}

function SimpleTable({ headers, children }: { headers: string[]; children: React.ReactNode }) {
  return <Card className="overflow-hidden bg-card/75"><Table><TableHeader><TableRow>{headers.map((header) => <TableHead key={header}>{header}</TableHead>)}</TableRow></TableHeader><TableBody>{children}</TableBody></Table></Card>;
}
