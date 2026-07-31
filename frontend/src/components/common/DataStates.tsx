import { AlertTriangle, Inbox, LoaderCircle } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export function LoadingState({ label = "Carregando dados demonstrativos…" }: { label?: string }) {
  return <Card><CardContent className="flex min-h-52 flex-col items-center justify-center gap-3 p-8 text-center"><LoaderCircle className="size-7 animate-spin text-primary" /><p className="text-sm text-muted-foreground">{label}</p><div className="mt-3 h-2 w-40 animate-pulse rounded bg-muted" /></CardContent></Card>;
}

export function EmptyState({ title = "Nenhum item encontrado", description = "Ajuste os filtros ou crie um registro demonstrativo.", action }: { title?: string; description?: string; action?: ReactNode }) {
  return <Card><CardContent className="flex min-h-52 flex-col items-center justify-center p-8 text-center"><div className="rounded-full bg-muted p-3"><Inbox className="size-6 text-muted-foreground" /></div><h3 className="mt-4 font-semibold">{title}</h3><p className="mt-1 max-w-md text-sm text-muted-foreground">{description}</p>{action && <div className="mt-5">{action}</div>}</CardContent></Card>;
}

export function ErrorState({ message = "Não foi possível carregar os dados demonstrativos.", onRetry }: { message?: string; onRetry?: () => void }) {
  return <Card><CardContent className="flex min-h-52 flex-col items-center justify-center p-8 text-center"><div className="rounded-full bg-rose-400/10 p-3"><AlertTriangle className="size-6 text-rose-400" /></div><h3 className="mt-4 font-semibold">Algo não saiu como esperado</h3><p className="mt-1 max-w-md text-sm text-muted-foreground">{message}</p>{onRetry && <Button className="mt-5" variant="outline" onClick={onRetry}>Tentar novamente</Button>}</CardContent></Card>;
}
