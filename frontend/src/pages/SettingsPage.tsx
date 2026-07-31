import { Database, Palette, Save, Settings2, ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";

import { PageHeader } from "@/components/common/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";

export function SettingsPage() {
  return <div className="space-y-6"><PageHeader eyebrow="Preferências do protótipo" title="Configurações" description="Representação visual dos parâmetros futuros. Nenhuma regra definitiva é salva ou aplicada." actions={<Button disabled><Save className="size-4" />Salvar configurações</Button>} />
    <div className="grid gap-5 xl:grid-cols-2"><SettingsCard icon={Settings2} title="Parâmetros gerais"><Field label="Nome do ambiente"><Input defaultValue="Ambiente demonstrativo" /></Field><Field label="Moeda"><Select defaultValue="BRL"><option value="BRL">Real brasileiro (BRL)</option></Select></Field><Field label="Fuso horário"><Select defaultValue="America/Sao_Paulo"><option value="America/Sao_Paulo">America/Sao_Paulo</option></Select></Field></SettingsCard>
      <SettingsCard icon={ShieldCheck} title="Políticas financeiras"><SettingRow label="Política de arredondamento" value="A definir" /><SettingRow label="Parâmetros de PJR" value="A definir" /><SettingRow label="Precisão monetária" value="Decimal / NUMERIC(14,2)" /><p className="rounded-xl border border-amber-400/20 bg-amber-400/10 p-4 text-sm text-amber-300">Nenhuma fórmula financeira definitiva está implementada.</p></SettingsCard>
      <SettingsCard icon={Palette} title="Preferências visuais"><Field label="Tema padrão"><Select defaultValue="dark"><option value="dark">Escuro</option><option value="light">Claro</option><option value="system">Sistema</option></Select></Field><Field label="Densidade de tabelas"><Select defaultValue="comfortable"><option value="comfortable">Confortável</option><option value="compact">Compacta</option></Select></Field><Field label="Formato de datas"><Input defaultValue="dd/mm/aaaa" disabled /></Field></SettingsCard>
      <SettingsCard icon={Database} title="Origem operacional futura"><SettingRow label="Fonte" value="Cadastro de Clientes" /><SettingRow label="Integração local" value="LocalFileSource — futura" /><SettingRow label="Integração remota" value="SharePointSource — futura" /><SettingRow label="Status" value="Não configurada" /><Badge variant="neutral">Nenhum Excel lido</Badge></SettingsCard>
    </div>
    <Card className="bg-card/75"><CardHeader><CardTitle className="text-base">Status possíveis dos aportes</CardTitle></CardHeader><CardContent className="flex flex-wrap gap-3"><Badge variant="info">Disponível</Badge><Badge variant="warning">Parcialmente alocado</Badge><Badge variant="success">Alocado</Badge><Badge variant="neutral">Encerrado</Badge></CardContent></Card>
  </div>;
}

function SettingsCard({ icon: Icon, title, children }: { icon: typeof Settings2; title: string; children: ReactNode }) { return <Card className="bg-card/75"><CardHeader><CardTitle className="flex items-center gap-2 text-base"><Icon className="size-5 text-primary" />{title}</CardTitle></CardHeader><CardContent className="space-y-4">{children}</CardContent></Card>; }
function Field({ label, children }: { label: string; children: ReactNode }) { return <label className="block space-y-2"><span className="text-sm font-medium">{label}</span>{children}</label>; }
function SettingRow({ label, value }: { label: string; value: string }) { return <div className="flex items-center justify-between gap-4 border-b border-border/60 pb-3 text-sm last:border-0"><span className="text-muted-foreground">{label}</span><span className="text-right font-medium">{value}</span></div>; }
