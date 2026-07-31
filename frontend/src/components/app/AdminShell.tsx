import {
  BarChart3, Bell, ChevronLeft, ChevronRight, CircleDollarSign, FileChartColumn,
  Gauge, Landmark, Menu, Moon, PanelLeftClose, Search, Settings, Shuffle,
  Sun, Users, WalletCards, X,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import { AppLink } from "@/components/app/AppLink";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

interface AdminShellProps { path: string; navigate: (path: string) => void; children: ReactNode; }

const navItems = [
  { path: "/dashboard", label: "Dashboard", icon: Gauge },
  { path: "/investidores", label: "Investidores", icon: Users },
  { path: "/aportes", label: "Aportes", icon: WalletCards },
  { path: "/rateio", label: "Rateio", icon: Shuffle },
  { path: "/contratos", label: "Contratos", icon: FileChartColumn },
  { path: "/tesouraria", label: "Tesouraria", icon: Landmark },
  { path: "/relatorios", label: "Relatórios", icon: BarChart3 },
  { path: "/sincronizacao", label: "Sincronização", icon: CircleDollarSign },
  { path: "/configuracoes", label: "Configurações", icon: Settings },
];

const labelByPath = Object.fromEntries(navItems.map((item) => [item.path, item.label]));

function Breadcrumbs({ path, navigate }: { path: string; navigate: (path: string) => void }) {
  const segments = path.split("/").filter(Boolean);
  const rootPath = `/${segments[0] ?? "dashboard"}`;
  const rootLabel = labelByPath[rootPath] ?? "Dashboard";
  return <nav aria-label="Navegação estrutural" className="flex items-center gap-1.5 text-xs text-muted-foreground"><AppLink to={rootPath} onNavigate={navigate} className="transition hover:text-foreground">{rootLabel}</AppLink>{segments.length > 1 && <><ChevronRight className="size-3.5" /><span className="text-foreground">Detalhe demonstrativo</span></>}</nav>;
}

export function AdminShell({ path, navigate, children }: AdminShellProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [theme, setTheme] = useState<"dark" | "light">(() => localStorage.getItem("remo-theme") === "light" ? "light" : "dark");

  useEffect(() => { document.documentElement.classList.toggle("dark", theme === "dark"); document.documentElement.dataset.theme = theme; localStorage.setItem("remo-theme", theme); }, [theme]);
  useEffect(() => setMobileOpen(false), [path]);

  const sidebar = <div className="flex h-full flex-col">
    <div className={cn("flex h-20 items-center border-b border-border px-5", collapsed && "justify-center px-3")}>
      <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-300 to-indigo-500 text-sm font-black text-slate-950">RF</div>
      {!collapsed && <div className="ml-3"><p className="font-semibold tracking-tight">Remo Funding</p><p className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Gestão de capital</p></div>}
    </div>
    <div className={cn("px-4 pt-5", collapsed && "px-2")}><Badge variant="warning" className={cn("w-full justify-center py-1.5", collapsed && "px-1 text-[9px]")}>{collapsed ? "DEMO" : "Ambiente demonstrativo"}</Badge></div>
    <nav aria-label="Menu principal" className="mt-5 flex-1 space-y-1 overflow-y-auto px-3">{navItems.map(({ path: itemPath, label, icon: Icon }) => {
      const active = path === itemPath || path.startsWith(`${itemPath}/`);
      return <AppLink key={itemPath} to={itemPath} onNavigate={navigate} title={collapsed ? label : undefined} aria-current={active ? "page" : undefined} className={cn("group flex h-11 items-center rounded-xl px-3 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring", active ? "bg-primary/12 text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground", collapsed && "justify-center px-0")}><Icon className="size-[18px] shrink-0" />{!collapsed && <span className="ml-3">{label}</span>}</AppLink>;
    })}</nav>
    <div className="border-t border-border p-3"><button type="button" onClick={() => setCollapsed((value) => !value)} className="hidden h-10 w-full items-center justify-center rounded-lg text-muted-foreground transition hover:bg-muted hover:text-foreground lg:flex" aria-label={collapsed ? "Expandir menu" : "Recolher menu"}><PanelLeftClose className={cn("size-4 transition", collapsed && "rotate-180")} />{!collapsed && <span className="ml-2 text-xs">Recolher menu</span>}</button>{!collapsed && <div className="mt-2 rounded-xl bg-muted/50 p-3"><p className="text-xs font-medium">Dados 100% fictícios</p><p className="mt-1 text-[11px] leading-4 text-muted-foreground">Nenhuma operação é gravada no Supabase.</p></div>}</div>
  </div>;

  return <div className="min-h-screen bg-background text-foreground">
    <aside className={cn("fixed inset-y-0 left-0 z-40 hidden border-r border-border bg-sidebar transition-[width] duration-200 lg:block", collapsed ? "w-[76px]" : "w-[252px]")}>{sidebar}</aside>
    {mobileOpen && <div className="fixed inset-0 z-50 lg:hidden"><button className="absolute inset-0 bg-slate-950/75" onClick={() => setMobileOpen(false)} aria-label="Fechar menu" /><aside className="relative h-full w-[286px] border-r border-border bg-sidebar shadow-2xl">{sidebar}<Button className="absolute right-3 top-3" variant="ghost" size="icon" onClick={() => setMobileOpen(false)} aria-label="Fechar menu"><X className="size-5" /></Button></aside></div>}
    <div className={cn("transition-[padding] duration-200", collapsed ? "lg:pl-[76px]" : "lg:pl-[252px]")}>
      <header className="sticky top-0 z-30 flex h-20 items-center gap-3 border-b border-border bg-background/85 px-4 backdrop-blur-xl sm:px-6">
        <Button variant="ghost" size="icon" className="lg:hidden" onClick={() => setMobileOpen(true)} aria-label="Abrir menu"><Menu className="size-5" /></Button>
        <div className="min-w-0 flex-1"><Breadcrumbs path={path} navigate={navigate} /></div>
        <label className="relative hidden w-full max-w-sm md:block"><Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" /><span className="sr-only">Busca global demonstrativa</span><Input className="pl-9" placeholder="Buscar investidores, aportes, contratos…" /></label>
        <Button variant="ghost" size="icon" aria-label="Notificações demonstrativas" className="relative"><Bell className="size-5" /><span className="absolute right-2 top-2 size-2 rounded-full bg-primary" /></Button>
        <Button variant="outline" size="icon" onClick={() => setTheme((value) => value === "dark" ? "light" : "dark")} aria-label={theme === "dark" ? "Ativar tema claro" : "Ativar tema escuro"}>{theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}</Button>
      </header>
      <main className="mx-auto max-w-[1600px] p-4 sm:p-6 lg:p-8">{children}</main>
      <footer className="flex flex-col gap-2 border-t border-border px-6 py-5 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between"><span>Remo Funding · Protótipo visual funcional</span><span className="flex items-center gap-1"><ChevronLeft className="size-3" /> Sem Excel · Sem gravações · Somente mocks</span></footer>
    </div>
  </div>;
}
