import { CalendarDays } from "lucide-react";

import { Select } from "@/components/ui/select";

export function PeriodSelector({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return <label className="relative flex items-center"><CalendarDays className="pointer-events-none absolute left-3 size-4 text-muted-foreground" /><span className="sr-only">Período</span><Select className="pl-9" value={value} onChange={(event) => onChange(event.target.value)}><option value="30">Últimos 30 dias</option><option value="90">Últimos 90 dias</option><option value="180">Últimos 6 meses</option><option value="365">Últimos 12 meses</option></Select></label>;
}
