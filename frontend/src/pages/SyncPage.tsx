import {
  ArrowUpCircle,
  CheckCircle2,
  Cloud,
  Download,
  Eye,
  FileSpreadsheet,
  History,
  Link2,
  RefreshCw,
  Unlink,
} from "lucide-react";
import { useCallback, useEffect, useState, type ReactNode } from "react";

import { ErrorState, LoadingState } from "@/components/common/DataStates";
import { FeedbackBanner, type Feedback } from "@/components/common/FeedbackBanner";
import { Modal } from "@/components/common/Modal";
import { PageHeader } from "@/components/common/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatDateTime } from "@/lib/formatters";
import { onedriveOAuthErrorMessage } from "@/lib/onedriveOAuth";
import { integrationsApi } from "@/services/integrationsApi";
import type {
  BatchCountComparison,
  BatchDataCounts,
  BatchQualityCounts,
  OperationalBatchDetail,
  OperationalBatchSummary,
  OperationalSourceStatus,
} from "@/types/integrations";

function megabytes(bytes: number | null): string {
  return bytes === null
    ? "—"
    : `${(bytes / 1024 / 1024).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} MB`;
}

function connectionLabel(status: OperationalSourceStatus["connection_status"]): string {
  return {
    CONNECTED: "Conectado",
    DISCONNECTED: "Não conectado",
    RECONNECT_REQUIRED: "Reconexão necessária",
    FILE_NOT_FOUND: "Arquivo não encontrado",
  }[status];
}

function updateLabel(status: OperationalSourceStatus["update_status"]): string {
  return {
    UNKNOWN: "Verificação pendente",
    CURRENT: "Atualizado",
    UPDATE_AVAILABLE: "Nova versão disponível",
    FILE_NOT_FOUND: "Arquivo não encontrado",
    RECONNECT_REQUIRED: "Reconexão necessária",
    ERROR: "Erro na verificação",
  }[status];
}

function shortHash(value: string | null): string {
  return value ? `${value.slice(0, 12)}…${value.slice(-8)}` : "—";
}

export function SyncPage() {
  const [source, setSource] = useState<OperationalSourceStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [action, setAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [oauthCallbackFailed, setOauthCallbackFailed] = useState(false);
  const [batches, setBatches] = useState<OperationalBatchSummary[]>([]);
  const [batchesLoading, setBatchesLoading] = useState(true);
  const [batchesError, setBatchesError] = useState<string | null>(null);
  const [selectedBatch, setSelectedBatch] = useState<OperationalBatchDetail | null>(null);
  const [batchDetailLoading, setBatchDetailLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setSource(await integrationsApi.status());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Falha ao carregar a integração.");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadBatches = useCallback(async () => {
    setBatchesLoading(true);
    setBatchesError(null);
    try {
      const result = await integrationsApi.listBatches();
      setBatches(result.items);
    } catch (caught) {
      setBatchesError(caught instanceof Error ? caught.message : "Falha ao carregar os batches.");
    } finally {
      setBatchesLoading(false);
    }
  }, []);

  const openBatch = async (batchId: number) => {
    setBatchDetailLoading(true);
    setFeedback(null);
    try {
      setSelectedBatch(await integrationsApi.getBatch(batchId));
    } catch (caught) {
      setFeedback({
        tone: "error",
        message: caught instanceof Error ? caught.message : "Falha ao abrir o batch.",
      });
    } finally {
      setBatchDetailLoading(false);
    }
  };

  useEffect(() => { void load(); }, [load]);
  useEffect(() => { void loadBatches(); }, [loadBatches]);
  useEffect(() => {
    const parameters = new URLSearchParams(window.location.search);
    const result = parameters.get("onedrive");
    if (result === "connected") {
      setOauthCallbackFailed(false);
      setFeedback({ tone: "success", message: "OneDrive conectado com segurança." });
    }
    if (result === "error") {
      setOauthCallbackFailed(true);
      setFeedback({
        tone: "error",
        message: onedriveOAuthErrorMessage(parameters.get("error_code")),
      });
    }
  }, []);

  const run = async (name: string, operation: () => Promise<void>) => {
    setAction(name);
    setFeedback(null);
    try {
      await operation();
      await load();
      await loadBatches();
    } catch (caught) {
      setFeedback({
        tone: "error",
        message: caught instanceof Error ? caught.message : "Não foi possível concluir a ação.",
      });
    } finally {
      setAction(null);
    }
  };

  if (loading && !source) return <LoadingState label="Carregando a fonte operacional…" />;
  if (error && !source) return <ErrorState message={error} onRetry={() => void load()} />;
  if (!source) return null;

  const connected = source.connection_status === "CONNECTED";
  const needsConnection = source.connection_status === "DISCONNECTED"
    || source.connection_status === "RECONNECT_REQUIRED";
  const isOneDrive = source.source_type === "onedrive";
  const canSynchronize = source.source_type === "local"
    || (connected && source.update_status !== "CURRENT");

  const promoteSelectedBatch = async () => {
    if (!selectedBatch?.promotion_eligible) return;
    if (!window.confirm(
      "Esta ação tornará este batch a versão operacional utilizada por Vendas e Receita. Deseja continuar?",
    )) return;
    setAction("promote");
    try {
      const result = await integrationsApi.promoteBatch(selectedBatch.id);
      await loadBatches();
      setSelectedBatch(await integrationsApi.getBatch(selectedBatch.id));
      setFeedback({
        tone: "success",
        message: `Batch #${result.source_batch_id} promovido com sucesso.`,
      });
    } catch (caught) {
      setFeedback({
        tone: "error",
        message: caught instanceof Error ? caught.message : "Não foi possível promover o batch.",
      });
    } finally {
      setAction(null);
    }
  };

  return <div className="space-y-6">
    <PageHeader
      eyebrow="Administração"
      title="Sincronização operacional"
      description="Controle manual da fonte do Cadastro de Clientes. Sincronizar cria um batch para revisão e nunca promove dados automaticamente."
      actions={<Badge variant={connected ? "success" : "neutral"}>{connectionLabel(source.connection_status)}</Badge>}
    />
    <FeedbackBanner feedback={feedback} onClose={() => setFeedback(null)} />

    <Card className="bg-card/80">
      <CardHeader><CardTitle className="flex items-center gap-2"><Cloud className="size-5 text-sky-400" />Fonte operacional</CardTitle></CardHeader>
      <CardContent className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
        <Info label="Fonte" value={isOneDrive ? "OneDrive Personal" : "Arquivo local"} />
        <Info label="Status" value={connectionLabel(source.connection_status)} />
        <Info label="Situação" value={updateLabel(source.update_status)} />
        <Info label="Arquivo" value={source.file_name ?? "Cadastro de Clientes.xlsm"} />
        <Info label="Última alteração no OneDrive" value={source.modified_at ? formatDateTime(source.modified_at) : "—"} />
        <Info label="Tamanho" value={megabytes(source.size)} />
        <Info label="Última sincronização" value={source.last_sync_at ? formatDateTime(source.last_sync_at) : "—"} />
        <Info label="Último batch" value={source.last_batch_id === null ? "—" : `#${source.last_batch_id}`} />
        <Info label="SHA-256" value={shortHash(source.last_sync_sha256)} mono />
        {source.file_path && <div className="md:col-span-2 xl:col-span-3"><Info label="Caminho oficial" value={source.file_path.split("/").filter(Boolean).join(" / ")} /></div>}
      </CardContent>
    </Card>

    <div className="flex flex-wrap gap-3">
      {isOneDrive && (needsConnection || oauthCallbackFailed) && <Button disabled={action !== null} onClick={() => void run("connect", async () => {
        setOauthCallbackFailed(false);
        const result = await integrationsApi.connect();
        window.location.assign(result.authorization_url);
      })}><Link2 className="size-4" />{oauthCallbackFailed ? "Tentar conectar novamente" : source.connection_status === "RECONNECT_REQUIRED" ? "Reconectar OneDrive" : "Conectar OneDrive"}</Button>}
      {isOneDrive && connected && <Button variant="outline" disabled={action !== null} onClick={() => void run("check", async () => {
        const updated = await integrationsApi.checkUpdate();
        setSource(updated);
        setFeedback({ tone: "success", message: updated.update_status === "CURRENT" ? "O arquivo está atualizado." : "Nova versão disponível para sincronização." });
      })}><RefreshCw className={`size-4 ${action === "check" ? "animate-spin" : ""}`} />Verificar atualização</Button>}
      {canSynchronize && <Button disabled={action !== null} onClick={() => void run("sync", async () => {
        const result = await integrationsApi.synchronize();
        setFeedback({ tone: "success", message: result.message });
      })}><Download className="size-4" />Sincronizar</Button>}
      {isOneDrive && source.connection_status !== "DISCONNECTED" && <Button variant="danger" disabled={action !== null} onClick={() => {
        if (!window.confirm("Desconectar o OneDrive? Os batches e dados operacionais serão preservados.")) return;
        void run("disconnect", async () => {
          await integrationsApi.disconnect();
          setFeedback({ tone: "success", message: "OneDrive desconectado. O histórico foi preservado." });
        });
      }}><Unlink className="size-4" />Desconectar</Button>}
    </div>

    <Card className="bg-card/80">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <History className="size-5 text-sky-400" />Histórico de sincronizações / Batches
        </CardTitle>
      </CardHeader>
      <CardContent>
        {batchesLoading && <LoadingState label="Carregando histórico de batches…" />}
        {batchesError && !batchesLoading && <ErrorState message={batchesError} onRetry={() => void loadBatches()} />}
        {!batchesLoading && !batchesError && batches.length === 0 && (
          <p className="text-sm text-muted-foreground">Nenhum batch operacional foi criado.</p>
        )}
        {!batchesLoading && !batchesError && batches.length > 0 && (
          <Table>
            <TableHeader><TableRow>
              <TableHead>Batch</TableHead><TableHead>Data / origem</TableHead>
              <TableHead>Arquivo / hash</TableHead><TableHead>Dados</TableHead>
              <TableHead>Qualidade</TableHead><TableHead>Status</TableHead><TableHead />
            </TableRow></TableHeader>
            <TableBody>{batches.map((batch) => <TableRow key={batch.id}>
              <TableCell><p className="font-semibold">#{batch.id}</p><p className="text-xs text-muted-foreground">{batch.initiated_by?.name ?? "Usuário não registrado"}</p></TableCell>
              <TableCell><p>{formatDateTime(batch.started_at)}</p><p className="text-xs text-muted-foreground">{batch.source_type === "ONEDRIVE" ? "OneDrive" : "Local"}</p></TableCell>
              <TableCell><p className="max-w-52 truncate">{batch.source_name ?? "—"}</p><p className="font-mono text-xs text-muted-foreground">{shortHash(batch.source_sha256)}</p></TableCell>
              <TableCell><BatchDataCompact counts={batch.data_counts} /></TableCell>
              <TableCell><BatchQualityCompact counts={batch.quality_counts} /></TableCell>
              <TableCell><div className="space-y-1"><Badge variant={batch.status === "succeeded" ? "success" : "neutral"}>{batch.status === "succeeded" ? "Sucedido" : batch.status}</Badge><p className="text-xs text-muted-foreground">{batch.promotion ? batch.promotion.is_current ? "Promovido atual" : "Promovido" : "Não promovido"}</p></div></TableCell>
              <TableCell><Button size="sm" variant="outline" disabled={batchDetailLoading} onClick={() => void openBatch(batch.id)}><Eye className="size-4" />Revisar</Button></TableCell>
            </TableRow>)}</TableBody>
          </Table>
        )}
      </CardContent>
    </Card>

    <Card className="border-dashed bg-card/60"><CardContent className="flex gap-4 p-5"><FileSpreadsheet className="mt-0.5 size-5 shrink-0 text-emerald-400" /><div><p className="font-medium">Pipeline operacional preservado</p><p className="mt-1 text-sm leading-6 text-muted-foreground">Somente as quatro abas autorizadas são lidas da cópia temporária. O SHA-256 evita batches duplicados e a promoção continua sendo uma ação administrativa separada.</p></div><CheckCircle2 className="ml-auto size-5 shrink-0 text-emerald-400" /></CardContent></Card>

    <Modal
      open={selectedBatch !== null}
      title={selectedBatch ? `Revisão do batch #${selectedBatch.id}` : "Revisão do batch"}
      description="A revisão não altera a versão operacional atual."
      onClose={() => setSelectedBatch(null)}
      footer={selectedBatch && <>
        <Button variant="outline" onClick={() => setSelectedBatch(null)}>Fechar</Button>
        {selectedBatch.promotion_eligible && <Button disabled={action !== null} onClick={() => void promoteSelectedBatch()}><ArrowUpCircle className="size-4" />{action === "promote" ? "Promovendo…" : "Promover batch"}</Button>}
      </>}
    >
      {selectedBatch && <BatchReview batch={selectedBatch} />}
    </Modal>
  </div>;
}

function Info({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return <div><p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p><p className={`mt-1 break-words text-sm ${mono ? "font-mono" : "font-medium"}`}>{value}</p></div>;
}

function BatchDataCompact({ counts }: { counts: BatchDataCounts }) {
  return <div className="whitespace-nowrap text-xs leading-5 text-muted-foreground">
    <p>Clientes: {integer(counts.bcli_cadastro)}</p><p>Contratos: {integer(counts.dfen_contrato)}</p>
    <p>Empréstimos: {integer(counts.econ_emprestimos)}</p><p>Amortizações: {integer(counts.econ_amortizacoes)}</p>
  </div>;
}

function BatchQualityCompact({ counts }: { counts: BatchQualityCounts }) {
  return <div className="whitespace-nowrap text-xs leading-5 text-muted-foreground">
    <p>Valid: {integer(counts.valid)}</p><p>Warning: {integer(counts.warning)}</p>
    <p>Divergent: {integer(counts.divergent)}</p><p>Invalid: {integer(counts.invalid)}</p>
  </div>;
}

function BatchReview({ batch }: { batch: OperationalBatchDetail }) {
  return <div className="space-y-6">
    <ReviewSection title="Resumo"><div className="grid gap-4 sm:grid-cols-2">
      <Info label="Fonte" value={batch.source_type === "ONEDRIVE" ? "OneDrive" : "Local"} />
      <Info label="Arquivo" value={batch.source_name ?? "—"} />
      <Info label="Data" value={formatDateTime(batch.started_at)} />
      <Info label="Status" value={batch.status === "succeeded" ? "Sucedido" : batch.status} />
      <div className="sm:col-span-2"><Info label="SHA-256" value={batch.source_sha256} mono /></div>
    </div></ReviewSection>
    <ReviewSection title="Dados"><div className="grid grid-cols-2 gap-3">
      <Metric label="Clientes" value={batch.data_counts.bcli_cadastro} />
      <Metric label="Contratos" value={batch.data_counts.dfen_contrato} />
      <Metric label="Empréstimos" value={batch.data_counts.econ_emprestimos} />
      <Metric label="Amortizações" value={batch.data_counts.econ_amortizacoes} />
    </div></ReviewSection>
    <ReviewSection title="Qualidade"><div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <Metric label="Valid" value={batch.quality_counts.valid} />
      <Metric label="Warning" value={batch.quality_counts.warning} />
      <Metric label="Divergent" value={batch.quality_counts.divergent} />
      <Metric label="Invalid" value={batch.quality_counts.invalid} />
    </div></ReviewSection>
    <ReviewSection title="Comparação com a promoção atual">
      <p className="mb-3 text-xs text-muted-foreground">Promoção atual: {batch.comparison.current_promotion_id ? `#${batch.comparison.current_promotion_id}, batch #${batch.comparison.current_source_batch_id}` : "nenhuma"}</p>
      <div className="space-y-3"><Comparison label="Vendas" value={batch.comparison.sales} /><Comparison label="Receitas" value={batch.comparison.revenue} /><Comparison label="Clientes" value={batch.comparison.clients} /><Comparison label="Empréstimos" value={batch.comparison.loans} /></div>
    </ReviewSection>
    {batch.promotion ? <div className="rounded-xl border border-emerald-400/25 bg-emerald-400/10 p-4 text-sm"><p className="font-medium">Batch promovido {batch.promotion.is_current ? "e atualmente em uso" : ""}</p><p className="mt-1 text-muted-foreground">{formatDateTime(batch.promotion.promoted_at)} · {batch.promotion.promoted_by?.name ?? "Usuário não registrado"}</p></div> : <div className="rounded-xl border border-amber-400/25 bg-amber-400/10 p-4 text-sm"><p className="font-medium">{batch.promotion_eligibility_reason}</p>{batch.promotion_eligible && <p className="mt-2 text-muted-foreground">Esta ação tornará este batch a versão operacional utilizada por Vendas e Receita.</p>}</div>}
  </div>;
}

function ReviewSection({ title, children }: { title: string; children: ReactNode }) {
  return <section><h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">{title}</h3>{children}</section>;
}

function Metric({ label, value }: { label: string; value: number }) {
  return <div className="rounded-xl border border-border/70 bg-background/40 p-3"><p className="text-xs text-muted-foreground">{label}</p><p className="mt-1 text-lg font-semibold">{integer(value)}</p></div>;
}

function Comparison({ label, value }: { label: string; value: BatchCountComparison }) {
  const difference = `${value.difference > 0 ? "+" : ""}${integer(value.difference)}`;
  return <div className="rounded-xl border border-border/70 p-3 text-sm"><p className="font-medium">{label}</p><div className="mt-2 grid grid-cols-3 gap-2 text-xs text-muted-foreground"><span>Atual<br /><strong className="text-foreground">{integer(value.current)}</strong></span><span>Após promoção<br /><strong className="text-foreground">{integer(value.candidate)}</strong></span><span>Diferença<br /><strong className={value.difference >= 0 ? "text-emerald-400" : "text-rose-400"}>{difference}</strong></span></div></div>;
}

function integer(value: number): string { return value.toLocaleString("pt-BR"); }
