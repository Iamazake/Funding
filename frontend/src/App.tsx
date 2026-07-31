import { FileQuestion } from "lucide-react";
import { useEffect } from "react";

import { AdminShell } from "@/components/app/AdminShell";
import { EmptyState } from "@/components/common/DataStates";
import { Button } from "@/components/ui/button";
import { useRouter } from "@/hooks/useRouter";
import { AllocationPage } from "@/pages/AllocationPage";
import { ContributionDetailPage } from "@/pages/ContributionDetailPage";
import { ContributionsPage } from "@/pages/ContributionsPage";
import { ContractsPage } from "@/pages/ContractsPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { InvestorDetailPage } from "@/pages/InvestorDetailPage";
import { InvestorsPage } from "@/pages/InvestorsPage";
import { ReportsPage } from "@/pages/ReportsPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { SyncPage } from "@/pages/SyncPage";
import { TreasuryPage } from "@/pages/TreasuryPage";

function App() {
  const { path, navigate } = useRouter();

  useEffect(() => {
    if (path === "/") navigate("/dashboard");
  }, [path, navigate]);

  const content = resolveRoute(path, navigate);
  return <AdminShell path={path === "/" ? "/dashboard" : path} navigate={navigate}>{content}</AdminShell>;
}

function resolveRoute(path: string, navigate: (path: string) => void) {
  if (path === "/" || path === "/dashboard") return <DashboardPage />;
  if (path === "/investidores") return <InvestorsPage navigate={navigate} />;
  const investorMatch = path.match(/^\/investidores\/([^/]+)$/);
  if (investorMatch) return <InvestorDetailPage id={investorMatch[1]} navigate={navigate} />;
  if (path === "/aportes") return <ContributionsPage navigate={navigate} />;
  const contributionMatch = path.match(/^\/aportes\/([^/]+)$/);
  if (contributionMatch) return <ContributionDetailPage id={contributionMatch[1]} navigate={navigate} />;
  if (path === "/rateio") return <AllocationPage />;
  if (path === "/contratos") return <ContractsPage />;
  if (path === "/tesouraria") return <TreasuryPage />;
  if (path === "/relatorios") return <ReportsPage />;
  if (path === "/sincronizacao") return <SyncPage />;
  if (path === "/configuracoes") return <SettingsPage />;
  return <EmptyState title="Página não encontrada" description="A rota solicitada não existe no protótipo demonstrativo." action={<Button onClick={() => navigate("/dashboard")}><FileQuestion className="size-4" />Ir para o dashboard</Button>} />;
}

export default App;
