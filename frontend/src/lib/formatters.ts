import type { Cents } from "@/types/funding";

const integerFormatter = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });
const dateFormatter = new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC" });

export function parseMoneyToCents(value: string): bigint {
  const normalized = value.trim().replace(/^\+/, "");
  if (!/^-?\d+(\.\d{1,2})?$/.test(normalized)) throw new Error("Valor monetário inválido");
  const negative = normalized.startsWith("-");
  const unsigned = negative ? normalized.slice(1) : normalized;
  const [integerPart, decimalPart = ""] = unsigned.split(".");
  const result = BigInt(integerPart) * 100n + BigInt(decimalPart.padEnd(2, "0"));
  return negative ? -result : result;
}

export function parseBrazilianMoneyToCents(value: string): bigint | null {
  const sanitized = value.replace(/R\$/gi, "").replace(/\s/g, "").trim();
  if (!sanitized) return 0n;
  if (!/^-?\d{1,3}(\.\d{3})*(,\d{0,2})?$|^-?\d+(,\d{0,2})?$/.test(sanitized)) return null;
  try {
    return parseMoneyToCents(sanitized.replace(/\./g, "").replace(",", "."));
  } catch {
    return null;
  }
}

export function centsToMoney(value: bigint): string {
  const negative = value < 0n;
  const absolute = negative ? -value : value;
  return `${negative ? "-" : ""}${absolute / 100n}.${(absolute % 100n).toString().padStart(2, "0")}`;
}

export function formatCents(value: bigint): string {
  const negative = value < 0n;
  const absolute = negative ? -value : value;
  return `${negative ? "-" : ""}R$ ${integerFormatter.format(absolute / 100n)},${(absolute % 100n).toString().padStart(2, "0")}`;
}

export function formatCentsAmount(value: Cents): string {
  return /^-?\d+$/.test(value) ? formatCents(BigInt(value)) : "Valor inválido";
}

export function formatMoney(value: string): string {
  return formatCents(parseMoneyToCents(value));
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(`${value.slice(0, 10)}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? value : dateFormatter.format(date);
}

export function formatDateTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(date);
}

export function formatPercent(value: string): string {
  return formatPercentage(value);
}

export function formatPercentage(value: string | null | undefined, suffix = "%"): string {
  if (value === null || value === undefined || value.trim() === "") return "Não informado";
  const parsed = Number(value.replace(",", "."));
  if (!Number.isFinite(parsed)) return value;
  return `${new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 4 }).format(parsed)}${suffix}`;
}

export function maskDocument(value: string): string {
  const digits = value.replace(/\D/g, "");
  if (digits.length === 11) return `${digits.slice(0, 3)}.***.***-${digits.slice(-2)}`;
  if (digits.length === 14) return `${digits.slice(0, 2)}.***.***/****-${digits.slice(-2)}`;
  return "Documento demonstrativo";
}

export function sumMoney(values: string[]): string {
  return centsToMoney(values.reduce((total, value) => total + parseMoneyToCents(value), 0n));
}

export function currencyInputToCents(value: string): Cents | null {
  const parsed = parseBrazilianMoneyToCents(value);
  return parsed === null ? null : parsed.toString();
}
