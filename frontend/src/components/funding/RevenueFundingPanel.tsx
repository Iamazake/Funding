import { RotateCcw } from "lucide-react";

import { EmptyState } from "@/components/common/DataStates";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { decimalMoneyToCents } from "@/lib/fundingFormat";
import { formatPercentage } from "@/lib/formatters";
import { formatOperationalMoney } from "@/lib/operationalFormat";
import type { RevenueDistribution } from "@/types/fundingApi";

export function RevenueFundingPanel({ distribution, saving, onDistribute, onReverse }: { distribution: RevenueDistribution; saving: boolean; onDistribute: () => void; onReverse: () => void }) {
  const gap = decimalMoneyToCents(distribution.unidentified_principal) !== 0n
    || decimalMoneyToCents(distribution.unidentified_interest) !== 0n
    || decimalMoneyToCents(distribution.unidentified_discount) !== 0n;
  const canDistribute = distribution.status === "READY" || distribution.status === "REVERSED";
  return <Card className="overflow-hidden bg-card/75">
    <CardHeader className="flex-row items-center justify-between gap-3"><div><CardTitle className="text-base">RATEIO FUNDING</CardTitle><p className="mt-1 text-sm text-muted-foreground">Snapshot da composição da Venda na data do processamento.</p></div><div className="flex gap-2"><StatusBadge status={distribution.status} />{canDistribute && <Button disabled={saving} onClick={onDistribute}>{saving ? "Processando…" : "Processar rateio"}</Button>}{distribution.status === "DISTRIBUTED" && <Button variant="outline" disabled={saving} onClick={onReverse}><RotateCcw className="size-4" />Reverter</Button>}</div></CardHeader>
    <CardContent className="space-y-4 p-6 pt-0">
      {distribution.reason && <p className={distribution.status === "DIVERGENT" ? "text-sm text-rose-400" : "text-sm text-muted-foreground"}>{distribution.reason}</p>}
      {distribution.status === "PENDING_FUNDING" && <EmptyState title="Funding ainda não informado. Rateio pendente." description="A Receita permanece operacional e nenhum valor foi lançado no ledger." />}
      <div className="grid gap-3 text-sm sm:grid-cols-2 xl:grid-cols-4"><Metric label="Fonte principal" value={distribution.primary_source_name ?? "Não identificada"} /><Metric label="Principal original" value={formatOperationalMoney(distribution.principal_amount)} /><Metric label="Juros originais" value={formatOperationalMoney(distribution.interest_amount)} /><Metric label="Desconto original" value={formatOperationalMoney(distribution.discount_amount)} /></div>
      {distribution.items.length > 0 && <Table><TableHeader><TableRow><TableHead>Fonte</TableHead><TableHead>Investidor / aporte</TableHead><TableHead>Percentual</TableHead><TableHead>Principal</TableHead><TableHead>Juros</TableHead><TableHead>Desconto</TableHead><TableHead>Total</TableHead></TableRow></TableHeader><TableBody>{distribution.items.map((item) => <TableRow key={item.id}><TableCell>{item.source_type === "REMO_CAPITAL" ? "Capital REMO" : "Aporte"}</TableCell><TableCell>{item.investor_name ?? "REMO"}<p className="text-xs text-muted-foreground">{item.contribution_code ?? "Capital próprio"}</p></TableCell><TableCell>{formatPercentage(item.percentage)}</TableCell><TableCell>{formatOperationalMoney(item.principal_amount)}</TableCell><TableCell>{formatOperationalMoney(item.interest_amount)}</TableCell><TableCell>{formatOperationalMoney(item.discount_amount)}</TableCell><TableCell>{formatOperationalMoney(item.total_amount)}</TableCell></TableRow>)}{gap && <TableRow className="font-medium text-amber-400"><TableCell>Não identificado</TableCell><TableCell>Gap da composição</TableCell><TableCell>—</TableCell><TableCell>{formatOperationalMoney(distribution.unidentified_principal)}</TableCell><TableCell>{formatOperationalMoney(distribution.unidentified_interest)}</TableCell><TableCell>{formatOperationalMoney(distribution.unidentified_discount)}</TableCell><TableCell>{formatOperationalMoney(distribution.unidentified_total)}</TableCell></TableRow>}</TableBody></Table>}
    </CardContent>
  </Card>;
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div><p className="text-xs uppercase tracking-wider text-muted-foreground">{label}</p><p className="mt-1 font-medium">{value}</p></div>;
}
