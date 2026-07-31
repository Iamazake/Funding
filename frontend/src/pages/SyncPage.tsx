import { CloudOff, FileSpreadsheet, LockKeyhole, Share2 } from "lucide-react";

import { PageHeader } from "@/components/common/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function SyncPage() {
  return <div className="space-y-6"><PageHeader eyebrow="Etapa futura" title="Sincronização operacional" description="A integração com o Cadastro de Clientes foi intencionalmente adiada e nenhum arquivo foi lido pelo protótipo." actions={<Badge variant="neutral">Não configurada</Badge>} />
    <Card className="overflow-hidden border-dashed bg-card/75"><CardContent className="flex min-h-[360px] flex-col items-center justify-center p-8 text-center"><div className="relative"><div className="rounded-3xl bg-muted p-6"><CloudOff className="size-12 text-muted-foreground" /></div><span className="absolute -bottom-2 -right-2 rounded-full border-4 border-card bg-amber-400 p-2 text-slate-950"><LockKeyhole className="size-4" /></span></div><h2 className="mt-8 text-xl font-semibold">Nenhuma sincronização executada</h2><p className="mt-2 max-w-xl text-sm leading-6 text-muted-foreground">A futura fonte operacional continuará sendo o arquivo Cadastro de Clientes. A conexão poderá usar LocalFileSource na etapa local e SharePointSource/Microsoft Graph posteriormente.</p><Button className="mt-6" disabled>Disponível em etapa futura</Button></CardContent></Card>
    <div className="grid gap-4 md:grid-cols-2"><Card className="bg-card/75"><CardHeader><CardTitle className="flex items-center gap-2 text-base"><FileSpreadsheet className="size-5 text-emerald-400" />LocalFileSource</CardTitle></CardHeader><CardContent><p className="text-sm leading-6 text-muted-foreground">Planejado para ler somente uma cópia local controlada. Não implementado neste protótipo.</p></CardContent></Card><Card className="bg-card/75"><CardHeader><CardTitle className="flex items-center gap-2 text-base"><Share2 className="size-5 text-sky-400" />SharePointSource</CardTitle></CardHeader><CardContent><p className="text-sm leading-6 text-muted-foreground">Planejado para Microsoft Graph em fase posterior. Nenhuma conexão foi configurada.</p></CardContent></Card></div>
  </div>;
}
