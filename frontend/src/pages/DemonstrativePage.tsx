import { Construction, LockKeyhole } from "lucide-react";

import { PageHeader } from "@/components/common/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";

export function DemonstrativePage({ eyebrow, title, description, scope }: { eyebrow: string; title: string; description: string; scope: string }) {
  return <div className="space-y-6"><PageHeader eyebrow={eyebrow} title={title} description={description} actions={<Badge variant="neutral">Demonstrativo nesta sprint</Badge>} /><Card className="border-dashed bg-card/75"><CardContent className="flex min-h-[360px] flex-col items-center justify-center p-8 text-center"><span className="rounded-3xl bg-muted p-6"><Construction className="size-12 text-muted-foreground" /></span><h2 className="mt-7 text-xl font-semibold">Escopo preservado para etapa posterior</h2><p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">{scope}</p><div className="mt-6 flex items-center gap-2 rounded-full border border-border px-4 py-2 text-xs text-muted-foreground"><LockKeyhole className="size-4" />Nenhuma integração real ou regra definitiva foi iniciada</div></CardContent></Card></div>;
}
