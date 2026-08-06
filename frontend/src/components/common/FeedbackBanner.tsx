import { CheckCircle2, TriangleAlert, X } from "lucide-react";

import { Button } from "@/components/ui/button";

export interface Feedback { tone: "success" | "error"; message: string; }

export function FeedbackBanner({ feedback, onClose }: { feedback: Feedback | null; onClose: () => void }) {
  if (!feedback) return null;
  const Icon = feedback.tone === "success" ? CheckCircle2 : TriangleAlert;
  return <div role="status" className={`flex items-center gap-3 rounded-xl border p-4 text-sm ${feedback.tone === "success" ? "border-emerald-400/20 bg-emerald-400/10 text-emerald-300" : "border-rose-400/20 bg-rose-400/10 text-rose-300"}`}><Icon className="size-5 shrink-0" /><p className="flex-1">{feedback.message}</p><Button variant="ghost" size="icon" onClick={onClose} aria-label="Fechar mensagem"><X className="size-4" /></Button></div>;
}
