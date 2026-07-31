import type { ReactNode } from "react";

interface PageHeaderProps { eyebrow?: string; title: string; description: string; actions?: ReactNode; }

export function PageHeader({ eyebrow, title, description, actions }: PageHeaderProps) {
  return <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
    <div className="max-w-3xl">{eyebrow && <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-primary">{eyebrow}</p>}<h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h1><p className="mt-2 text-sm leading-6 text-muted-foreground sm:text-base">{description}</p></div>
    {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
  </div>;
}
