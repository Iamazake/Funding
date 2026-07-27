import { Activity, Database, Server } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { getHealth, type HealthResponse } from "@/lib/api";

type LoadState =
  | { kind: "loading" }
  | { kind: "ready"; health: HealthResponse }
  | { kind: "error" };

function App() {
  const [state, setState] = useState<LoadState>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();

    getHealth(controller.signal)
      .then((health) => setState({ kind: "ready", health }))
      .catch(() => {
        if (!controller.signal.aborted) {
          setState({ kind: "error" });
        }
      });

    return () => controller.abort();
  }, []);

  const connected =
    state.kind === "ready" &&
    state.health.api === "ok" &&
    state.health.database === "connected";

  return (
    <main className="min-h-screen bg-background text-foreground">
      <div className="mx-auto flex min-h-screen max-w-5xl items-center px-6 py-16">
        <section className="w-full space-y-8">
          <div className="space-y-3">
            <Badge variant="outline">Fase 0 · Fundação</Badge>
            <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
              Remo Funding
            </h1>
            <p className="max-w-2xl text-lg text-muted-foreground">
              FastAPI, React e PostgreSQL gerenciado prontos para receber as
              próximas fases — sem antecipar regras de negócio.
            </p>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <StatusCard
              icon={Activity}
              title="Frontend"
              description="React 18 + TypeScript + Vite"
              ok
            />
            <StatusCard
              icon={Server}
              title="API"
              description={
                state.kind === "loading"
                  ? "Verificando FastAPI…"
                  : state.kind === "ready"
                    ? "FastAPI respondeu"
                    : "FastAPI indisponível"
              }
              ok={state.kind === "ready"}
            />
            <StatusCard
              icon={Database}
              title="Banco"
              description={
                state.kind === "loading"
                  ? "Verificando Supabase…"
                  : connected
                    ? "PostgreSQL conectado"
                    : "PostgreSQL indisponível"
              }
              ok={connected}
            />
          </div>
        </section>
      </div>
    </main>
  );
}

type StatusCardProps = {
  icon: typeof Activity;
  title: string;
  description: string;
  ok: boolean;
};

function StatusCard({
  icon: Icon,
  title,
  description,
  ok,
}: StatusCardProps) {
  return (
    <Card>
      <CardHeader className="space-y-3">
        <div className="flex items-center justify-between">
          <Icon className="size-5 text-primary" aria-hidden="true" />
          <span
            className={`size-2.5 rounded-full ${
              ok ? "bg-emerald-500" : "bg-amber-500"
            }`}
            aria-label={ok ? "Disponível" : "Aguardando"}
          />
        </div>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
          {ok ? "Operacional" : "Aguardando"}
        </p>
      </CardContent>
    </Card>
  );
}

export default App;

