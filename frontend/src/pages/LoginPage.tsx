import { LoaderCircle, LockKeyhole } from "lucide-react";
import { useState, type FormEvent } from "react";

import { FeedbackBanner, type Feedback } from "@/components/common/FeedbackBanner";
import { FormField } from "@/components/common/FormField";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/contexts/AuthContext";
import { AuthApiError } from "@/services/authApi";

export function LoginPage({ onAuthenticated }: { onAuthenticated: () => void }) {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault(); setLoading(true); setFeedback(null);
    try {
      await login(email, password);
      onAuthenticated();
    } catch (error) {
      const message = error instanceof AuthApiError && error.status === null
        ? "Não foi possível conectar ao servidor."
        : error instanceof AuthApiError && error.status === 429
          ? error.message
          : "E-mail ou senha inválidos.";
      setFeedback({ tone: "error", message });
    } finally { setLoading(false); }
  };

  return <main className="flex min-h-screen items-center justify-center bg-[#071525] p-4"><Card className="w-full max-w-md border-white/10 bg-card/95 shadow-2xl"><CardContent className="p-8"><div className="mb-8 text-center"><div className="mx-auto flex size-14 items-center justify-center rounded-2xl bg-emerald-400 font-black text-[#071525]">RF</div><h1 className="mt-4 text-2xl font-semibold">Funding REMO</h1><p className="mt-2 text-sm text-muted-foreground">Acesso restrito a usuários autorizados</p></div><FeedbackBanner feedback={feedback} onClose={() => setFeedback(null)} /><form className="mt-5 space-y-4" onSubmit={submit}><FormField label="E-mail"><Input autoComplete="username" type="email" required value={email} onChange={(event) => setEmail(event.target.value)} /></FormField><FormField label="Senha"><Input autoComplete="current-password" type="password" required value={password} onChange={(event) => setPassword(event.target.value)} /></FormField><Button className="w-full" type="submit" disabled={loading}>{loading ? <LoaderCircle className="size-4 animate-spin" /> : <LockKeyhole className="size-4" />}{loading ? "Entrando…" : "Entrar"}</Button></form></CardContent></Card></main>;
}
