export function formatMonthlyRate(rate: string): string {
  if (!/^\d+(\.\d+)?$/.test(rate)) return rate;
  const [integer, fraction = ""] = rate.split(".");
  const digits = `${integer}${fraction}`.replace(/^0+(?=\d)/, "");
  const scale = fraction.length;
  const scaled = BigInt(digits || "0") * 100n;
  const denominator = 10n ** BigInt(scale);
  const whole = scaled / denominator;
  const remainder = (scaled % denominator).toString().padStart(scale, "0").replace(/0+$/, "");
  return `${whole}${remainder ? `,${remainder}` : ""}% a.m.`;
}

export function brazilianMoneyToDecimal(value: string): string | null {
  const sanitized = value.replace(/R\$/gi, "").replace(/\s/g, "").trim();
  if (!/^\d{1,3}(\.\d{3})*(,\d{0,2})?$|^\d+(,\d{0,2})?$/.test(sanitized)) return null;
  const normalized = sanitized.replace(/\./g, "").replace(",", ".");
  const [integer, fraction = ""] = normalized.split(".");
  return `${integer}.${fraction.padEnd(2, "0")}`;
}

export function decimalToBrazilianInput(value: string): string {
  const [integer, fraction = ""] = value.split(".");
  const grouped = integer.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return `${grouped},${fraction.padEnd(2, "0").slice(0, 2)}`;
}

export function decimalMoneyToCents(value: string): bigint | null {
  if (!/^\d+(\.\d{1,2})?$/.test(value)) return null;
  const [integer, fraction = ""] = value.split(".");
  return BigInt(integer) * 100n + BigInt(fraction.padEnd(2, "0"));
}
