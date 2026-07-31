import { Badge } from "@/components/ui/badge";

const labels: Record<string, string> = {
  active: "Ativo", pending: "Pendente", inactive: "Inativo", available: "Disponível",
  partially_allocated: "Parcialmente alocado", allocated: "Alocado", closed: "Encerrado",
  partial: "Funding parcial", funded: "Financiado", scheduled: "Programado", completed: "Concluído", paid: "Pago",
};

export function StatusBadge({ status }: { status: string }) {
  const variant = status === "active" || status === "funded" || status === "completed" || status === "paid" ? "success"
    : status === "pending" || status === "partial" || status === "partially_allocated" || status === "scheduled" ? "warning"
      : status === "inactive" || status === "closed" ? "neutral" : "info";
  return <Badge variant={variant}>{labels[status] ?? status}</Badge>;
}
