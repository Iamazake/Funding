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
  return <div className="space-y-6"><PageHeader eyebrow="Preferências" title="Configurações" description="Parâmetros do ambiente integrado e dos módulos que ainda permanecem demonstrativos." actions={<Button variant="outline" onClick={() => setRestoreOpen(true)}><RefreshCcw className="size-4" />Restaurar módulos demonstrativos</Button>} />
    <FeedbackBanner feedback={feedback} onClose={() => setFeedback(null)} />
    <div className="grid gap-5 xl:grid-cols-2"><SettingsCard icon={Settings2} title="Ambiente"><SettingRow label="Nome" value="Ambiente de desenvolvimento integrado" /><SettingRow label="Moeda" value="Real brasileiro (BRL)" /><SettingRow label="Fuso horário" value="America/Sao_Paulo" /><SettingRow label="Persistência" value="API FastAPI + Supabase" /></SettingsCard>
      <SettingsCard icon={ShieldCheck} title="Políticas financeiras"><SettingRow label="Valores monetários" value="Decimal/NUMERIC no backend" /><SettingRow label="Taxa mensal" value="Fração decimal (2% = 0,02)" /><SettingRow label="Rateio" value="Participação histórica por fonte" /><SettingRow label="Arredondamento" value="Maiores restos em centavos" /><p className="rounded-xl border border-emerald-400/20 bg-emerald-400/10 p-4 text-sm text-emerald-300">As regras reais de funding, alocação e retorno de principal estão integradas ao backend.</p></SettingsCard>
      <SettingsCard icon={Palette} title="Preferências visuais"><label className="block space-y-2"><span className="text-sm font-medium">Tema padrão</span><Select defaultValue="dark"><option value="dark">Escuro</option><option value="light">Claro</option></Select></label><SettingRow label="Cor estrutural" value="Azul-marinho" /><SettingRow label="Destaque positivo" value="Verde" /><SettingRow label="Formato de datas" value="dd/mm/aaaa" /></SettingsCard>
      <SettingsCard icon={Database} title="Fontes e privacidade"><SettingRow label="Módulos integrados" value="Investidores, Aportes, Vendas e Receita" /><SettingRow label="Armazenamento do domínio" value="PostgreSQL Supabase via API" /><SettingRow label="Receita" value="Base operacional integrada" /><SettingRow label="Supabase" value="Leitura e gravação pelo backend" /><SettingRow label="Excel" value="Origem operacional controlada" /><SettingRow label="Backend" value="FastAPI integrado" /><div className="flex flex-wrap gap-2"><Badge variant="neutral">Integração real</Badge><Badge variant="neutral">Migrations aplicadas</Badge><Badge variant="neutral">Autenticação por sessão segura</Badge></div></SettingsCard></div>
    <ConfirmDialog open={restoreOpen} title="Restaurar módulos demonstrativos?" description="Somente os módulos que ainda usam o repositório demonstrativo local serão restaurados. Investidores, Aportes, Vendas e Receita não serão alterados." confirmLabel="Restaurar módulos" danger onCancel={() => setRestoreOpen(false)} onConfirm={() => { fundingRepository.restoreDemoData(); setRestoreOpen(false); setFeedback({ tone: "success", message: "Módulos demonstrativos restaurados." }); }} />
  </div>;
}

function SettingsCard({ icon: Icon, title, children }: { icon: typeof Settings2; title: string; children: ReactNode }) { return <Card className="bg-card/75"><CardHeader><CardTitle className="flex items-center gap-2 text-base"><Icon className="size-5 text-primary" />{title}</CardTitle></CardHeader><CardContent className="space-y-4">{children}</CardContent></Card>; }
function SettingRow({ label, value }: { label: string; value: string }) { return <div className="flex items-center justify-between gap-4 border-b border-border/60 pb-3 text-sm last:border-0"><span className="text-muted-foreground">{label}</span><span className="text-right font-medium">{value}</span></div>; }
