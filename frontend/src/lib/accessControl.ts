import type { UserRole } from "@/types/auth";

const adminPaths = ["/configuracoes", "/sincronizacao"];

export function canAccessPath(role: UserRole, path: string): boolean {
  if (role === "ADMIN") return true;
  return !adminPaths.some((adminPath) => path === adminPath || path.startsWith(`${adminPath}/`));
}
