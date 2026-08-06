import { AppLink } from "@/components/app/AppLink";
import { cn } from "@/lib/utils";

export interface TabItem { value: string; label: string; path?: string; }

export function Tabs({ items, value, onChange, navigate }: { items: TabItem[]; value: string; onChange?: (value: string) => void; navigate?: (path: string) => void }) {
  return <div className="flex gap-1 overflow-x-auto rounded-xl border border-border bg-card/70 p-1" role="tablist">
    {items.map((item) => {
      const classes = cn("whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium transition", value === item.value ? "bg-primary text-primary-foreground shadow-sm" : "text-muted-foreground hover:bg-muted hover:text-foreground");
      if (item.path && navigate) return <AppLink key={item.value} to={item.path} onNavigate={navigate} role="tab" aria-selected={value === item.value} className={classes}>{item.label}</AppLink>;
      return <button key={item.value} type="button" role="tab" aria-selected={value === item.value} className={classes} onClick={() => onChange?.(item.value)}>{item.label}</button>;
    })}
  </div>;
}
