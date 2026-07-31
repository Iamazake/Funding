import { Select } from "@/components/ui/select";

export type DemoViewState = "ready" | "loading" | "empty" | "error";

export function DemoStateSwitcher({ value, onChange }: { value: DemoViewState; onChange: (value: DemoViewState) => void }) {
  return <label className="flex items-center gap-2 text-xs text-muted-foreground"><span>Visualizar estado</span><Select className="h-8" value={value} onChange={(event) => onChange(event.target.value as DemoViewState)}><option value="ready">Com dados</option><option value="loading">Carregando</option><option value="empty">Vazio</option><option value="error">Erro</option></Select></label>;
}
