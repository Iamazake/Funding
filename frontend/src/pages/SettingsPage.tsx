import { Database, Palette, RefreshCcw, Settings2, ShieldCheck } from "lucide-react";
import { useState, type ReactNode } from "react";

import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { FeedbackBanner, type Feedback } from "@/components/common/FeedbackBanner";
import { PageHeader } from "@/components/common/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { fundingRepository } from "@/services/fundingService";

export function SettingsPage() {
  const [restoreOpen, setRestoreOpen] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  return <div className="space-y-6"><PageHeader eyebrow="Preferências" title="Configurações" description="Parâmetros do ambiente demonstrativo e restauração segura do conjunto fictício." actions={<Button variant="outline" onClick={() => setRestoreOpen(true)}><RefreshCcw className="size-4" />Restaurar dados demonstrativos</Button>} />
    <FeedbackBanner feedback={feedback} onClose={() => setFeedback(null)} />
    <div className="grid gap-5 xl:grid-cols-2"><SettingsCard icon={Settings2} title="Ambiente"><SettingRow label="Nome" value="Ambiente demonstrativo" /><SettingRow label="Moeda" value="Real brasileiro (BRL)" /><SettingRow label="Fuso horário" value="America/Sao_Paulo" /><SettingRow label="Persistência" value="localStorage deste navegador" /></SettingsCard>
      <SettingsCard icon={ShieldCheck} title="Políticas financeiras"><SettingRow label="Valores monetários" value="Strings inteiras de centavos" /><SettingRow label="Operações monetárias" value="bigint" /><SettingRow label="Parâmetros de PJR" value="A definir · valor informado" /><SettingRow label="Arredondamento definitivo" value="A definir" /><p className="rounded-xl border border-amber-400/20 bg-amber-400/10 p-4 text-sm text-amber-300">Nenhuma fórmula financeira definitiva está implementada.</p></SettingsCard>
      <SettingsCard icon={Palette} title="Preferências visuais"><label className="block space-y-2"><span className="text-sm font-medium">Tema padrão</span><Select defaultValue="dark"><option value="dark">Escuro</option><option value="light">Claro</option></Select></label><SettingRow label="Cor estrutural" value="Azul-marinho" /><SettingRow label="Destaque positivo" value="Verde" /><SettingRow label="Formato de datas" value="dd/mm/aaaa" /></SettingsCard>
      <SettingsCard icon={Database} title="Fontes e privacidade"><SettingRow label="Dados deste protótipo" value="Somente mocks fictícios" /><SettingRow label="Armazenamento do domínio" value="Versão demonstrativa v4" /><SettingRow label="Receita" value="Projeção das entradas existentes" /><SettingRow label="Supabase" value="Sem gravações" /><SettingRow label="Excel" value="Não acessado" /><SettingRow label="Backend" value="Preservado" /><div className="flex flex-wrap gap-2"><Badge variant="neutral">Sem dados reais</Badge><Badge variant="neutral">Sem migration</Badge><Badge variant="neutral">Sem autenticação</Badge></div></SettingsCard></div>
    <ConfirmDialog open={restoreOpen} title="Restaurar dados demonstrativos?" description="Todos os cadastros e alterações feitos neste navegador serão substituídos pelo conjunto fictício inicial." confirmLabel="Restaurar dados" danger onCancel={() => setRestoreOpen(false)} onConfirm={() => { fundingRepository.restoreDemoData(); setRestoreOpen(false); setFeedback({ tone: "success", message: "Dados demonstrativos restaurados." }); }} />
  </div>;
}

function SettingsCard({ icon: Icon, title, children }: { icon: typeof Settings2; title: string; children: ReactNode }) { return <Card className="bg-card/75"><CardHeader><CardTitle className="flex items-center gap-2 text-base"><Icon className="size-5 text-primary" />{title}</CardTitle></CardHeader><CardContent className="space-y-4">{children}</CardContent></Card>; }
function SettingRow({ label, value }: { label: string; value: string }) { return <div className="flex items-center justify-between gap-4 border-b border-border/60 pb-3 text-sm last:border-0"><span className="text-muted-foreground">{label}</span><span className="text-right font-medium">{value}</span></div>; }
