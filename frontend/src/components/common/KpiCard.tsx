import { ArrowDownRight, ArrowUpRight, Minus, type LucideIcon } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface KpiCardProps { label: string; value: string; helper?: string; variation?: string; direction?: "up" | "down" | "stable"; icon: LucideIcon; compact?: boolean; }

export function KpiCard({ label, value, helper, variation, direction = "stable", icon: Icon, compact }: KpiCardProps) {
  const TrendIcon = direction === "up" ? ArrowUpRight : direction === "down" ? ArrowDownRight : Minus;
  return <Card className="overflow-hidden bg-card/75"><CardContent className={cn("p-5", !compact && "sm:p-6")}>
    <div className="flex items-start justify-between"><div className="rounded-xl border border-primary/15 bg-primary/10 p-2.5"><Icon className="size-5 text-primary" aria-hidden="true" /></div>{variation && <span className={cn("flex items-center gap-1 text-xs font-medium", direction === "up" ? "text-emerald-400" : direction === "down" ? "text-rose-400" : "text-muted-foreground")}><TrendIcon className="size-3.5" />{variation}%</span>}</div>
    <p className="mt-5 text-sm text-muted-foreground">{label}</p><p className={cn("mt-1 font-semibold tracking-tight", compact ? "text-xl" : "text-2xl")}>{value}</p>{helper && <p className="mt-2 text-xs text-muted-foreground">{helper}</p>}
  </CardContent></Card>;
}
