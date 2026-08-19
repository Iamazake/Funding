import { FileQuestion } from "lucide-react";
import { useEffect } from "react";

import { AdminShell } from "@/components/app/AdminShell";
import { EmptyState, LoadingState } from "@/components/common/DataStates";
import { Button } from "@/components/ui/button";
import { useRouter } from "@/hooks/useRouter";
import { useAuth } from "@/contexts/AuthContext";
import { canAccessPath } from "@/lib/accessControl";
import { CapitalRemunerationsPage } from "@/pages/CapitalRemunerationsPage";
import { ContributionDetailPage } from "@/pages/ContributionDetailPage";
import { ContributionsPage } from "@/pages/ContributionsPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { InvestorDetailPage } from "@/pages/InvestorDetailPage";
import { InvestorsPage } from "@/pages/InvestorsPage";
import { ReportsPage, type ReportsSection } from "@/pages/ReportsPage";
import { RevenueDetailPage } from "@/pages/RevenueDetailPage";
import { RevenuePage } from "@/pages/RevenuePage";
import { RevenueDivergencesPage, RevenueMonthlySummaryPage, RevenuePendingPage } from "@/pages/RevenueWorkPages";
import { SalesBankValidationPage, SalesDetailPage, SalesDivergencesPage, SalesPage } from "@/pages/SalesPages";
import { SettingsPage } from "@/pages/SettingsPage";
import { LoginPage } from "@/pages/LoginPage";
import { SyncPage } from "@/pages/SyncPage";
import { TreasuryIncomingListPage } from "@/pages/TreasuryIncomingPages";
import { TreasuryPage, type TreasurySection } from "@/pages/TreasuryPage";
import { UsersPage } from "@/pages/UsersPage";

function legacyRedirect(path: string): string | null {
  if (path === "/") return "/dashboard";
  if (path === "/cadastro") return "/cadastro/investidores";
  if (path === "/investidores") return "/cadastro/investidores";
  if (path === "/aportes") return "/cadastro/aportes";
  if (path === "/rateio") return "/vendas";
  if (path.startsWith("/cadastro/prospects") || path.startsWith("/prospects")) return "/cadastro/investidores";
  if (path.startsWith("/cadastro/dividendos") || path.startsWith("/dividendos")) return "/cadastro/remuneracoes";
  if (path === "/vendas/nova") return "/vendas";
  if (path === "/contratos" || path === "/contratos/composicao" || path === "/contratos/alocacoes") return "/vendas";
  if (path === "/contratos/divergencias") return "/vendas/divergencias";
  const retiredContract = path.match(/^\/contratos\/([^/]+)(?:\/funding)?$/);
  if (retiredContract) return `/vendas/${retiredContract[1]}`;
  if (path === "/tesouraria/entradas") return "/receita/validacao-bancaria";
  const retiredIncoming = path.match(/^\/tesouraria\/entradas\/([^/]+)$/);
  if (retiredIncoming) return `/receita/${retiredIncoming[1]}`;
  if (path === "/tesouraria/saidas") return "/vendas";
  if (path === "/tesouraria/movimentacoes") return "/tesouraria/fluxo";
  if (path === "/relatorios") return "/relatorios/safra";
  const investor = path.match(/^\/investidores\/([^/]+)$/);
  if (investor) return `/cadastro/investidores/${investor[1]}`;
  const contribution = path.match(/^\/aportes\/([^/]+)$/);
  if (contribution) return `/cadastro/aportes/${contribution[1]}`;
  return null;
}

function App() {
  const { path, navigate } = useRouter();
  const { status, user, logout } = useAuth();
  const redirect = legacyRedirect(path); const effective = redirect ?? path;
  useEffect(() => { if (redirect) navigate(redirect, true); }, [redirect, navigate]);
  useEffect(() => {
    if (status === "anonymous" && path !== "/login") navigate("/login", true);
    if (status === "authenticated" && path === "/login") navigate("/dashboard", true);
  }, [status, path, navigate]);
  if (status === "loading") return <main className="min-h-screen bg-background p-8"><LoadingState label="Verificando sessão segura…" /></main>;
  if (status === "anonymous" || !user) return <LoginPage onAuthenticated={() => navigate("/dashboard", true)} />;
  if (!canAccessPath(user.role, effective)) return <AdminShell path={effective} navigate={navigate} user={user} onLogout={async () => { await logout(); navigate("/login", true); }}><EmptyState title="Acesso não autorizado" description="Seu perfil não possui permissão para acessar esta área administrativa." action={<Button onClick={() => navigate("/dashboard")}>Ir para o dashboard</Button>} /></AdminShell>;
  return <AdminShell path={effective} navigate={navigate} user={user} onLogout={async () => { await logout(); navigate("/login", true); }}>{resolveRoute(effective, navigate)}</AdminShell>;
}

function resolveRoute(path: string, navigate: (path: string) => void) {
  if (path === "/dashboard") return <DashboardPage />;
  if (path === "/cadastro/investidores") return <InvestorsPage navigate={navigate} />;
  const investor = path.match(/^\/cadastro\/investidores\/([^/]+)$/);
  if (investor) return <InvestorDetailPage id={investor[1]} navigate={navigate} />;
  if (path === "/cadastro/aportes") return <ContributionsPage navigate={navigate} />;
  const contribution = path.match(/^\/cadastro\/aportes\/([^/]+)$/);
  if (contribution) return <ContributionDetailPage id={contribution[1]} navigate={navigate} />;
  if (path === "/cadastro/remuneracoes") return <CapitalRemunerationsPage />;
  const remuneration = path.match(/^\/cadastro\/remuneracoes\/([^/]+)$/);
  if (remuneration) return <CapitalRemunerationsPage id={remuneration[1]} />;

  if (path === "/vendas") return <SalesPage navigate={navigate} />;
  if (path === "/vendas/divergencias") return <SalesDivergencesPage navigate={navigate} />;
  if (path === "/vendas/validacao-bancaria") return <SalesBankValidationPage navigate={navigate} />;
  const sale = path.match(/^\/vendas\/([^/]+)$/);
  if (sale) return <SalesDetailPage id={sale[1]} navigate={navigate} />;

  if (path === "/receita") return <RevenuePage navigate={navigate} />;
  if (path === "/receita/validacao-bancaria") return <TreasuryIncomingListPage navigate={navigate} />;
  if (path === "/receita/pendencias") return <RevenuePendingPage navigate={navigate} />;
  if (path === "/receita/divergencias") return <RevenueDivergencesPage navigate={navigate} />;
  if (path === "/receita/resumo-mensal") return <RevenueMonthlySummaryPage />;
  const revenue = path.match(/^\/receita\/([^/]+)$/);
  if (revenue) return <RevenueDetailPage id={revenue[1]} navigate={navigate} />;

  const treasury: Record<string, TreasurySection> = {
    "/tesouraria": "summary", "/tesouraria/fluxo": "flow",
    "/tesouraria/remuneracoes": "remunerations", "/tesouraria/conciliacao": "reconciliation",
    "/tesouraria/divergencias": "divergences",
  };
  if (treasury[path]) return <TreasuryPage section={treasury[path]} navigate={navigate} />;
  const reports: Record<string, ReportsSection> = {
    "/relatorios/safra": "harvest", "/relatorios/receita": "revenue",
    "/relatorios/funding": "funding", "/relatorios/pdd": "pdd",
    "/relatorios/fluxo-investidor": "investor-flow",
  };
  if (reports[path]) return <ReportsPage section={reports[path]} navigate={navigate} />;
  if (path === "/sincronizacao") return <SyncPage />;
  if (path === "/configuracoes") return <SettingsPage />;
  if (path === "/configuracoes/usuarios") return <UsersPage />;
  return <EmptyState title="Página não encontrada" action={<Button onClick={() => navigate("/dashboard")}><FileQuestion className="size-4" />Ir para o dashboard</Button>} />;
}

export default App;
