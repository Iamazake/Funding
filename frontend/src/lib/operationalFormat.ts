import { formatCentsAmount, formatPercentage } from "@/lib/formatters";

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

/** ECON rate fields are stored as decimal fractions: 0.12 means 12%. */
export function formatOperationalRate(
  value: string | null | undefined,
  monthly = false,
): string {
  if (value === null || value === undefined || value.trim() === "") return "Não informado";
  const parsed = Number(value.replace(",", "."));
  if (!Number.isFinite(parsed)) return value;
  const percentage = parsed * 100;
  const displayValue = Math.abs(percentage) < 0.00005 ? 0 : percentage;
  return formatPercentage(String(displayValue), monthly ? "% a.m." : "%");
}
