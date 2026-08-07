import { formatCentsAmount } from "@/lib/formatters";

export function decimalToCents(value: string | null | undefined): string {
  if (!value) return "0";
  const match = value.trim().match(/^(-?)(\d+)(?:\.(\d{1,2}))?$/);
  if (!match) return "0";
  const [, sign, units, fraction = ""] = match;
  const cents = `${units}${fraction.padEnd(2, "0")}`.replace(/^0+(?=\d)/, "");
  return `${sign}${cents}`;
}

export function formatOperationalMoney(value: string | null | undefined): string {
  return formatCentsAmount(decimalToCents(value));
}

export function formatRate(value: string | null | undefined): string {
  if (!value) return "Não informada";
  return `${value}%`;
}
