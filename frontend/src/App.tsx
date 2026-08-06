import { FileQuestion } from "lucide-react";
import { useEffect } from "react";

import { AdminShell } from "@/components/app/AdminShell";
import { EmptyState } from "@/components/common/DataStates";
import { Button } from "@/components/ui/button";
import { useRouter } from "@/hooks/useRouter";
import { CapitalRemunerationsPage } from "@/pages/CapitalRemunerationsPage";
import { ContributionDetailPage } from "@/pages/ContributionDetailPage";
import { ContributionsPage } from "@/pages/ContributionsPage";
import {
  ContractAllocationsPage, ContractCompositionPage, ContractDetailPage,
  ContractDivergencesPage, ContractsPage,
} from "@/pages/ContractsPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { InvestorDetailPage } from "@/pages/InvestorDetailPage";
import { InvestorsPage } from "@/pages/InvestorsPage";
import { ReportsPage } from "@/pages/ReportsPage";
import { RevenueDetailPage } from "@/pages/RevenueDetailPage";
import { RevenuePage } from "@/pages/RevenuePage";
import { RevenueDivergencesPage, RevenueMonthlySummaryPage, RevenuePendingPage } from "@/pages/RevenueWorkPages";
import { SettingsPage } from "@/pages/SettingsPage";
import { SyncPage } from "@/pages/SyncPage";
import { TreasuryIncomingDetailPage, TreasuryIncomingListPage } from "@/pages/TreasuryIncomingPages";
import { TreasuryPage, type TreasurySection } from "@/pages/TreasuryPage";

function legacyRedirect(path: string): string | null {
  if (path === "/") return "/dashboard";
  if (path === "/cadastro") return "/cadastro/investidores";
  if (path === "/investidores") return "/cadastro/investidores";
  if (path === "/aportes") return "/cadastro/aportes";
  if (path === "/rateio") return "/contratos/alocacoes";
  if (path.startsWith("/cadastro/prospects") || path.startsWith("/prospects")) return "/cadastro/investidores";
  if (path.startsWith("/cadastro/dividendos") || path.startsWith("/dividendos")) return "/cadastro/remuneracoes";
  if (path === "/vendas" || path === "/vendas/validacao-bancaria") return "/tesouraria/entradas";
  if (path === "/vendas/divergencias") return "/tesouraria/divergencias";
  if (path === "/vendas/nova") return "/contratos";
  const retiredSale = path.match(/^\/vendas\/([^/]+)$/);
  if (retiredSale) return `/contratos/${retiredSale[1]}`;
  if (path === "/tesouraria/movimentacoes") return "/tesouraria";
  const investor = path.match(/^\/investidores\/([^/]+)$/);
  if (investor) return `/cadastro/investidores/${investor[1]}`;
  const contribution = path.match(/^\/aportes\/([^/]+)$/);
  if (contribution) return `/cadastro/aportes/${contribution[1]}`;
  return null;
}

function App() {
  const { path, navigate } = useRouter();
  const redirect = legacyRedirect(path); const effective = redirect ?? path;
  useEffect(() => { if (redirect) navigate(redirect, true); }, [redirect, navigate]);
  return <AdminShell path={effective} navigate={navigate}>{resolveRoute(effective, navigate)}</AdminShell>;
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

  if (path === "/contratos") return <ContractsPage navigate={navigate} />;
  if (path === "/contratos/composicao") return <ContractCompositionPage navigate={navigate} />;
  if (path === "/contratos/alocacoes") return <ContractAllocationsPage />;
  if (path === "/contratos/divergencias") return <ContractDivergencesPage />;
  const contractFunding = path.match(/^\/contratos\/([^/]+)\/funding$/);
  if (contractFunding) return <ContractDetailPage id={contractFunding[1]} navigate={navigate} fundingOnly />;
  const contract = path.match(/^\/contratos\/([^/]+)$/);
  if (contract) return <ContractDetailPage id={contract[1]} navigate={navigate} />;

  if (path === "/receita") return <RevenuePage navigate={navigate} />;
  if (path === "/receita/pendencias") return <RevenuePendingPage navigate={navigate} />;
  if (path === "/receita/divergencias") return <RevenueDivergencesPage navigate={navigate} />;
  if (path === "/receita/resumo-mensal") return <RevenueMonthlySummaryPage />;
  const revenue = path.match(/^\/receita\/([^/]+)$/);
  if (revenue) return <RevenueDetailPage id={revenue[1]} navigate={navigate} />;

  if (path === "/tesouraria/entradas") return <TreasuryIncomingListPage navigate={navigate} />;
  const incoming = path.match(/^\/tesouraria\/entradas\/([^/]+)$/);
  if (incoming) return <TreasuryIncomingDetailPage id={incoming[1]} navigate={navigate} />;
  const treasury: Record<string, TreasurySection> = {
    "/tesouraria": "summary", "/tesouraria/saidas": "exits",
    "/tesouraria/remuneracoes": "remunerations", "/tesouraria/conciliacao": "reconciliation",
    "/tesouraria/divergencias": "divergences",
  };
  if (treasury[path]) return <TreasuryPage section={treasury[path]} navigate={navigate} />;
  if (path === "/relatorios") return <ReportsPage />;
  if (path === "/sincronizacao") return <SyncPage />;
  if (path === "/configuracoes") return <SettingsPage />;
  return <EmptyState title="Página não encontrada" action={<Button onClick={() => navigate("/dashboard")}><FileQuestion className="size-4" />Ir para o dashboard</Button>} />;
}

export default App;
