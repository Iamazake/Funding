import { ArrowLeft } from "lucide-react";

import { AppLink } from "@/components/app/AppLink";
import { OperationalBankValidationPage } from "@/components/funding/OperationalBankValidationPage";

export function TreasuryIncomingListPage({ navigate }: { navigate: (path: string) => void }) {
  return (
    <div className="space-y-6">
      <AppLink to="/receita" onNavigate={navigate} className="inline-flex items-center gap-2 text-sm text-muted-foreground">
        <ArrowLeft className="size-4" />Voltar para Receita
      </AppLink>
      <OperationalBankValidationPage kind="REVENUE" navigate={navigate} />
    </div>
  );
}
