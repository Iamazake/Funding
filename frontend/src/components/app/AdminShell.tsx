import {
  BarChart3, Bell, ChevronDown, ChevronRight, CircleDollarSign, FileText, Gauge,
  Landmark, Layers3, Menu, Moon, ReceiptText, RefreshCcw, Search, Settings, ShieldCheck, Sun, Users,
  WalletCards, X, type LucideIcon,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import { AppLink } from "@/components/app/AppLink";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

interface NavItem { path: string; label: string; icon: LucideIcon; }
interface NavGroup { label?: string; items: NavItem[]; }

const navGroups: NavGroup[] = [
  { items: [{ path: "/dashboard", label: "Dashboard", icon: Gauge }] },
  { label: "Cadastro", items: [
    { path: "/cadastro/investidores", label: "Investidores", icon: Users },
    { path: "/cadastro/aportes", label: "Aportes", icon: WalletCards },
    { path: "/cadastro/remuneracoes", label: "Remuneração de Capital", icon: CircleDollarSign },
  ] },
  { label: "Vendas", items: [
    { path: "/vendas", label: "Operações", icon: FileText },
    { path: "/vendas/divergencias", label: "Divergências", icon: RefreshCcw },
    { path: "/vendas/validacao-bancaria", label: "Validação bancária", icon: ShieldCheck },
  ] },
  { label: "Receita", items: [
    { path: "/receita", label: "Recebimentos", icon: ReceiptText },
    { path: "/receita/divergencias", label: "Divergências", icon: RefreshCcw },
    { path: "/receita/validacao-bancaria", label: "Validação bancária", icon: ShieldCheck },
  ] },
  { label: "Tesouraria", items: [
    { path: "/tesouraria", label: "Visão geral", icon: Landmark },
    { path: "/tesouraria/conciliacao", label: "Conciliação", icon: Gauge },
    { path: "/tesouraria/remuneracoes", label: "Remunerações", icon: CircleDollarSign },
    { path: "/tesouraria/divergencias", label: "Divergências", icon: RefreshCcw },
    { path: "/tesouraria/fluxo", label: "Fluxo consolidado", icon: BarChart3 },
  ] },
  { label: "Relatórios", items: [
    { path: "/relatorios/safra", label: "Safra", icon: BarChart3 },
    { path: "/relatorios/receita", label: "Receita", icon: ReceiptText },
    { path: "/relatorios/funding", label: "Funding", icon: Layers3 },
    { path: "/relatorios/pdd", label: "PDD", icon: ShieldCheck },
    { path: "/relatorios/fluxo-investidor", label: "FC Investidor(a)", icon: WalletCards },
  ] },
  { items: [{ path: "/sincronizacao", label: "Sincronização", icon: RefreshCcw }] },
  { items: [{ path: "/configuracoes", label: "Configurações", icon: Settings }] },
];

const allItems = navGroups.flatMap((group) => group.items);
function isActive(path: string, itemPath: string) {
  if (itemPath === "/receita") return path === itemPath || (/^\/receita\/[^/]+$/.test(path) && !["/receita/pendencias", "/receita/divergencias", "/receita/resumo-mensal", "/receita/validacao-bancaria"].includes(path));
  if (itemPath === "/vendas") return path === itemPath || (/^\/vendas\/[^/]+$/.test(path) && !["/vendas/divergencias", "/vendas/validacao-bancaria"].includes(path));
  if (itemPath === "/tesouraria") return path === itemPath;
  return path === itemPath || path.startsWith(`${itemPath}/`);
}

function NavEntry({ item, path, navigate }: { item: NavItem; path: string; navigate: (path: string) => void }) {
  const Icon = item.icon; const active = isActive(path, item.path);
  return <AppLink to={item.path} onNavigate={navigate} className={cn("flex h-10 items-center rounded-lg px-3 text-sm transition", active ? "bg-emerald-400/15 text-emerald-300" : "text-slate-400 hover:bg-white/5 hover:text-white")}><Icon className="size-4" /><span className="ml-3">{item.label}</span></AppLink>;
}

function Breadcrumbs({ path, navigate }: { path: string; navigate: (path: string) => void }) {
  const root = path.startsWith("/cadastro") ? "Cadastro" : path.startsWith("/vendas") ? "Vendas" : path.startsWith("/receita") ? "Receita" : path.startsWith("/tesouraria") ? "Tesouraria" : path.startsWith("/relatorios") ? "Relatórios" : undefined;
  const exact = allItems.find((item) => isActive(path, item.path));
  return <nav className="flex items-center gap-2 text-xs text-muted-foreground">{root && <><span>{root}</span><ChevronRight className="size-3" /></>}<AppLink to={exact?.path ?? "/dashboard"} onNavigate={navigate}>{exact?.label ?? "Detalhe"}</AppLink>{path.split("/").filter(Boolean).length > 2 && <><ChevronRight className="size-3" /><span>Detalhe</span></>}</nav>;
}

export function AdminShell({ path, navigate, children }: { path: string; navigate: (path: string) => void; children: ReactNode }) {
  const [mobile, setMobile] = useState(false);
  const [theme, setTheme] = useState<"dark" | "light">(() => window.localStorage.getItem("remo-theme") === "light" ? "light" : "dark");
  const [groups, setGroups] = useState<Record<string, boolean>>({ Cadastro: true, Vendas: true, Receita: true, Tesouraria: true, Relatórios: true });
  useEffect(() => { document.documentElement.classList.toggle("dark", theme === "dark"); window.localStorage.setItem("remo-theme", theme); }, [theme]);
  useEffect(() => setMobile(false), [path]);
  const sidebar = <div className="flex h-full flex-col bg-[#071525] text-slate-100"><div className="flex h-20 items-center border-b border-white/10 px-5"><div className="flex size-10 items-center justify-center rounded-xl bg-emerald-400 font-black text-[#071525]">RF</div><div className="ml-3"><p className="font-semibold">Remo Funding</p><p className="text-[10px] uppercase tracking-widest text-slate-400">Gestão de capital</p></div></div><div className="px-4 pt-4"><Badge variant="warning" className="w-full justify-center py-1.5">Ambiente demonstrativo</Badge></div><nav className="mt-4 flex-1 space-y-1 overflow-y-auto px-3">{navGroups.map((group, index) => group.label ? <div key={group.label}><button type="button" onClick={() => setGroups((current) => ({ ...current, [group.label!]: current[group.label!] === false }))} className="flex h-9 w-full items-center px-3 text-xs font-semibold uppercase tracking-widest text-slate-500">{group.label}<ChevronDown className={cn("ml-auto size-3", groups[group.label] === false && "-rotate-90")} /></button>{groups[group.label] !== false && <div className="ml-2 space-y-1 border-l border-white/10 pl-2">{group.items.map((item) => <NavEntry key={item.path} item={item} path={path} navigate={navigate} />)}</div>}</div> : group.items.map((item) => <NavEntry key={`${index}-${item.path}`} item={item} path={path} navigate={navigate} />))}</nav><div className="border-t border-white/10 p-4 text-xs text-slate-400">Dados fictícios · localStorage<br />Sem Excel · Sem Supabase</div></div>;
  return <div className="min-h-screen bg-background"><aside className="fixed inset-y-0 left-0 z-40 hidden w-[280px] lg:block">{sidebar}</aside>{mobile && <div className="fixed inset-0 z-50 lg:hidden"><button className="absolute inset-0 bg-black/70" onClick={() => setMobile(false)} /><aside className="relative h-full w-[300px]">{sidebar}<Button size="icon" variant="ghost" className="absolute right-2 top-2" onClick={() => setMobile(false)}><X className="size-5" /></Button></aside></div>}<div className="lg:pl-[280px]"><header className="sticky top-0 z-30 flex h-20 items-center gap-3 border-b bg-background/90 px-4 backdrop-blur sm:px-6"><Button size="icon" variant="ghost" className="lg:hidden" onClick={() => setMobile(true)}><Menu className="size-5" /></Button><div className="flex-1"><Breadcrumbs path={path} navigate={navigate} /></div><label className="relative hidden max-w-sm flex-1 md:block"><Search className="absolute left-3 top-3 size-4 text-muted-foreground" /><Input className="pl-9" placeholder="Buscar no ambiente demonstrativo…" /></label><Button size="icon" variant="ghost"><Bell className="size-5" /></Button><Button size="icon" variant="outline" onClick={() => setTheme((value) => value === "dark" ? "light" : "dark")}>{theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}</Button></header><main className="mx-auto max-w-[1680px] p-4 sm:p-6 lg:p-8">{children}</main><footer className="border-t px-6 py-5 text-xs text-muted-foreground">Remo Funding · Domínio demonstrativo · Sem integração real</footer></div></div>;
}
