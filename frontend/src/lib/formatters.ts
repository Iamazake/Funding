import type { Money } from "@/types/funding";

const currencyFormatter = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const dateFormatter = new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC" });

export function parseMoneyToCents(value: Money): bigint {
  const normalized = value.trim().replace(/^\+/, "");
  if (!/^-?\d+(\.\d{1,2})?$/.test(normalized)) {
    throw new Error("Valor monetário inválido");
  }

  const negative = normalized.startsWith("-");
  const unsigned = negative ? normalized.slice(1) : normalized;
  const [integerPart, decimalPart = ""] = unsigned.split(".");
  const cents = BigInt(integerPart) * 100n + BigInt(decimalPart.padEnd(2, "0"));
  return negative ? -cents : cents;
}

export function parseBrazilianMoneyToCents(value: string): bigint | null {
  const sanitized = value.replace(/R\$/gi, "").replace(/\s/g, "").trim();
  if (!sanitized) return 0n;
  if (!/^-?\d{1,3}(\.\d{3})*(,\d{0,2})?$|^-?\d+(,\d{0,2})?$/.test(sanitized)) {
    return null;
  }
  const normalized = sanitized.replace(/\./g, "").replace(",", ".");
  try {
    return parseMoneyToCents(normalized);
  } catch {
    return null;
  }
}

export function centsToMoney(cents: bigint): Money {
  const negative = cents < 0n;
  const absolute = negative ? -cents : cents;
  const integerPart = absolute / 100n;
  const decimalPart = (absolute % 100n).toString().padStart(2, "0");
  return `${negative ? "-" : ""}${integerPart}.${decimalPart}`;
}

export function formatMoney(value: Money): string {
  const cents = parseMoneyToCents(value);
  const safeNumber = Number(cents) / 100;
  return currencyFormatter.format(safeNumber);
}

export function formatCents(cents: bigint): string {
  return formatMoney(centsToMoney(cents));
}

export function formatDate(value: string | null): string {
  if (!value) return "—";
  const date = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? value : dateFormatter.format(date);
}

export function formatPercent(value: string): string {
  return `${value.replace(".", ",")}%`;
}

export function maskDocument(value: string): string {
  const digits = value.replace(/\D/g, "");
  if (digits.length === 11) return `${digits.slice(0, 3)}.***.***-${digits.slice(-2)}`;
  if (digits.length === 14) return `${digits.slice(0, 2)}.***.***/****-${digits.slice(-2)}`;
  return "Documento demonstrativo";
}

export function sumMoney(values: Money[]): Money {
  return centsToMoney(values.reduce((total, value) => total + parseMoneyToCents(value), 0n));
}
