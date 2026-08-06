import type { ReactNode } from "react";

export function FormField({ label, hint, children, className = "" }: { label: string; hint?: string; children: ReactNode; className?: string }) {
  return <label className={`block space-y-2 ${className}`}><span className="text-sm font-medium">{label}</span>{children}{hint && <span className="block text-xs text-muted-foreground">{hint}</span>}</label>;
}
