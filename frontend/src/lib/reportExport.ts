export type ExportCell = string | number;
export type ExportRow = Record<string, ExportCell>;

function escapeCsv(value: ExportCell): string {
  const text = String(value);
  return /[;"\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

export function reportRowsToCsv(rows: ExportRow[]): string {
  if (rows.length === 0) return "";
  const columns = Object.keys(rows[0]);
  return [columns.map(escapeCsv).join(";"), ...rows.map((row) => columns.map((column) => escapeCsv(row[column] ?? "")).join(";"))].join("\r\n");
}

export function downloadReportCsv(filename: string, rows: ExportRow[]): void {
  const blob = new Blob(["\uFEFF", reportRowsToCsv(rows)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob); const anchor = document.createElement("a");
  anchor.href = url; anchor.download = filename; anchor.click(); URL.revokeObjectURL(url);
}

export async function copyReportTable(rows: ExportRow[]): Promise<void> {
  const csv = reportRowsToCsv(rows);
  await navigator.clipboard.writeText(csv.replaceAll(";", "\t"));
}
