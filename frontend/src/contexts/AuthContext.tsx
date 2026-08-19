import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { authApi, AuthApiError } from "@/services/authApi";
import type { AppUser } from "@/types/auth";
import { AUTH_UNAUTHORIZED_EVENT } from "@/lib/api";

type AuthStatus = "loading" | "authenticated" | "anonymous";

interface AuthContextValue {
  status: AuthStatus;
  user: AppUser | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<AppUser | null>(null);

  const refresh = async () => {
    try {
      const current = await authApi.me();
      setUser(current);
      setStatus("authenticated");
    } catch (error) {
      setUser(null);
      setStatus("anonymous");
      if (!(error instanceof AuthApiError) || (error.status !== 401 && error.status !== 403)) throw error;
    }
  };

  useEffect(() => { void refresh().catch(() => undefined); }, []);
  useEffect(() => {
    const unauthorized = () => { setUser(null); setStatus("anonymous"); };
    window.addEventListener(AUTH_UNAUTHORIZED_EVENT, unauthorized);
    return () => window.removeEventListener(AUTH_UNAUTHORIZED_EVENT, unauthorized);
  }, []);

  const value = useMemo<AuthContextValue>(() => ({
    status,
    user,
    login: async (email, password) => {
      await authApi.login(email, password);
      const confirmedUser = await authApi.me();
      setUser(confirmedUser);
      setStatus("authenticated");
    },
    logout: async () => {
      try { await authApi.logout(); } finally { setUser(null); setStatus("anonymous"); }
    },
    refresh,
  }), [status, user]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// The hook intentionally shares this module with its provider.
// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth deve ser usado dentro de AuthProvider.");
  return context;
}
