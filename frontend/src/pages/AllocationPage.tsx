import { CheckCircle2, CircleDollarSign, ShieldAlert, Shuffle } from "lucide-react";
import { useCallback, useMemo, useState } from "react";

import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { ErrorState, LoadingState } from "@/components/common/DataStates";
import { PageHeader } from "@/components/common/PageHeader";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useAsyncData } from "@/hooks/useAsyncData";
import { centsToMoney, formatCents, formatMoney, parseBrazilianMoneyToCents, parseMoneyToCents } from "@/lib/formatters";
import { fundingService } from "@/services/fundingService";
import type { AllocationSimulationResult } from "@/types/funding";

export function AllocationPage() {
  const contractsLoader = useCallback(() => fundingService.contracts.listContracts(), []);
  const contributionsLoader = useCallback(() => fundingService.contributions.listContributions(), []);
  const contractsData = useAsyncData(contractsLoader);
  const contributionsData = useAsyncData(contributionsLoader);
  const [contractId, setContractId] = useState("");
  const [amounts, setAmounts] = useState<Record<string, string>>({});
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [result, setResult] = useState<AllocationSimulationResult | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const contracts = useMemo(() => contractsData.state.status === "success" ? contractsData.state.data : [], [contractsData.state]);
  const contributions = useMemo(() => contributionsData.state.status === "success" ? contributionsData.state.data.filter((item) => parseMoneyToCents(item.availableAmount) > 0n) : [], [contributionsData.state]);
  const selectedContract = contracts.find((item) => item.id === contractId);
  const requiredCents = selectedContract ? parseMoneyToCents(selectedContract.requiredFunding) : 0n;
  const alreadyAllocatedCents = selectedContract ? parseMoneyToCents(selectedContract.allocatedFunding) : 0n;
  const stillRequiredCents = requiredCents - alreadyAllocatedCents;
  const parsedAmounts = useMemo(() => contributions.map((item) => ({ contribution: item, cents: parseBrazilianMoneyToCents(amounts[item.id] ?? "") })), [contributions, amounts]);
  const totalCents = parsedAmounts.reduce((total, item) => total + (item.cents ?? 0n), 0n);
  const hasInvalid = parsedAmounts.some((item) => item.cents === null || (item.cents ?? 0n) > parseMoneyToCents(item.contribution.availableAmount));
  const exceedsContract = totalCents > stillRequiredCents;
  const canConfirm = Boolean(selectedContract) && totalCents > 0n && !hasInvalid && !exceedsContract;

  if (contractsData.state.status === "loading" || contributionsData.state.status === "loading") return <LoadingState label="Preparando experiência de rateio…" />;
  if (contractsData.state.status === "error" || contributionsData.state.status === "error") return <ErrorState onRetry={() => { contractsData.reload(); contributionsData.reload(); }} />;

  const confirm = async () => {
    if (!selectedContract || !canConfirm) return;
    setSubmitting(true);
    const simulation = await fundingService.allocations.simulateAllocation({ contractId: selectedContract.id, items: parsedAmounts.filter((item) => (item.cents ?? 0n) > 0n).map((item) => ({ contributionId: item.contribution.id, amount: centsToMoney(item.cents ?? 0n) })) });
    setResult(simulation); setSubmitting(false); setConfirmOpen(false);
    if (simulation.success) { setAmounts({}); contractsData.reload(); contributionsData.reload(); }
  };

  return <div className="space-y-6"><PageHeader eyebrow="Alocação de capital" title="Rateio demonstrativo" description="Combine quantos aportes forem necessários, valide os saldos e simule a alocação sem gravar no Supabase." actions={<Badge variant="warning">Estado local da sessão</Badge>} />
    {result && <div className={`flex items-start gap-3 rounded-xl border p-4 text-sm ${result.success ? "border-emerald-400/20 bg-emerald-400/10" : "border-rose-400/20 bg-rose-400/10"}`}>{result.success ? <CheckCircle2 className="size-5 shrink-0 text-emerald-400" /> : <ShieldAlert className="size-5 shrink-0 text-rose-400" />}<div><p className="font-medium">{result.message}</p><p className="mt-1 text-muted-foreground">Alocado: {formatMoney(result.allocatedAmount)} · Ainda necessário: {formatMoney(result.remainingAmount)}</p></div></div>}
    <div className="grid gap-5 xl:grid-cols-[1fr_360px]"><div className="space-y-5"><Card className="bg-card/75"><CardHeader><CardTitle className="flex items-center gap-2 text-base"><span className="flex size-7 items-center justify-center rounded-full bg-primary text-xs text-primary-foreground">1</span>Selecione o contrato fictício</CardTitle></CardHeader><CardContent><Select className="w-full" value={contractId} onChange={(event) => { setContractId(event.target.value); setResult(null); }}><option value="">Escolha um contrato disponível…</option>{contracts.filter((item) => item.status !== "funded").map((item) => <option key={item.id} value={item.id}>{item.code} · necessário {formatCents(parseMoneyToCents(item.requiredFunding) - parseMoneyToCents(item.allocatedFunding))}</option>)}</Select>{selectedContract && <div className="mt-4 grid gap-3 sm:grid-cols-3"><Summary label="Valor necessário" value={formatMoney(selectedContract.requiredFunding)} /><Summary label="Já alocado" value={formatMoney(selectedContract.allocatedFunding)} /><Summary label="Ainda necessário" value={formatCents(stillRequiredCents)} /></div>}</CardContent></Card>
      <Card className="bg-card/75"><CardHeader><CardTitle className="flex items-center gap-2 text-base"><span className="flex size-7 items-center justify-center rounded-full bg-primary text-xs text-primary-foreground">2</span>Distribua entre os aportes</CardTitle></CardHeader><CardContent className="space-y-3">{contributions.map((item) => { const parsed = parseBrazilianMoneyToCents(amounts[item.id] ?? ""); const exceeds = parsed !== null && parsed > parseMoneyToCents(item.availableAmount); return <div key={item.id} className={`grid gap-3 rounded-xl border p-4 md:grid-cols-[1fr_190px] ${exceeds || parsed === null ? "border-rose-400/40" : "border-border"}`}><div><div className="flex flex-wrap items-center gap-2"><p className="font-medium">{item.code}</p><StatusBadge status={item.status} /></div><p className="mt-1 text-sm text-muted-foreground">{item.investorName}</p><p className="mt-2 text-xs">Saldo livre: <span className="font-semibold text-emerald-400">{formatMoney(item.availableAmount)}</span></p></div><label className="space-y-1.5"><span className="text-xs font-medium text-muted-foreground">Valor a alocar</span><Input inputMode="decimal" value={amounts[item.id] ?? ""} onChange={(event) => setAmounts((current) => ({ ...current, [item.id]: event.target.value }))} placeholder="0,00" disabled={!selectedContract} />{exceeds && <span className="text-xs text-rose-400">Acima do saldo livre</span>}{parsed === null && <span className="text-xs text-rose-400">Formato inválido</span>}</label></div>; })}</CardContent></Card></div>
      <Card className="h-fit bg-card/75 xl:sticky xl:top-28"><CardHeader><CardTitle className="flex items-center gap-2 text-base"><Shuffle className="size-4 text-primary" />Resumo da alocação</CardTitle></CardHeader><CardContent className="space-y-4"><Summary label="Funding necessário" value={formatCents(stillRequiredCents)} /><Summary label="Total informado" value={formatCents(totalCents)} highlight /><Summary label="Valor ainda necessário" value={formatCents(stillRequiredCents - totalCents)} /><div className="h-2 overflow-hidden rounded-full bg-muted"><div className="h-full bg-gradient-to-r from-cyan-400 to-indigo-500 transition-all" style={{ width: `${stillRequiredCents > 0n ? Number(totalCents * 100n / stillRequiredCents > 100n ? 100n : totalCents * 100n / stillRequiredCents) : 0}%` }} /></div>{exceedsContract && <p className="rounded-lg bg-rose-400/10 p-3 text-xs text-rose-400">O total excede o valor ainda necessário.</p>}<Button className="w-full" disabled={!canConfirm || submitting} onClick={() => setConfirmOpen(true)}><CircleDollarSign className="size-4" />Revisar e confirmar</Button><p className="text-center text-[11px] leading-4 text-muted-foreground">Nenhuma regra financeira definitiva é aplicada.</p></CardContent></Card>
    </div>
    <ConfirmDialog open={confirmOpen} title="Confirmar rateio demonstrativo?" description={`Você está simulando ${formatCents(totalCents)} em ${parsedAmounts.filter((item) => (item.cents ?? 0n) > 0n).length} aporte(s).`} onCancel={() => setConfirmOpen(false)} onConfirm={() => void confirm()} />
  </div>;
}

function Summary({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) { return <div className="flex items-center justify-between gap-3 rounded-lg bg-muted/50 p-3"><span className="text-xs text-muted-foreground">{label}</span><span className={`text-sm font-semibold ${highlight ? "text-primary" : ""}`}>{value}</span></div>; }
