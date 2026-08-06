import { AlertCircle } from "lucide-react";

import { Modal } from "@/components/common/Modal";
import { Button } from "@/components/ui/button";

interface ConfirmDialogProps { open: boolean; title: string; description: string; confirmLabel?: string; danger?: boolean; onConfirm: () => void; onCancel: () => void; }

export function ConfirmDialog({ open, title, description, confirmLabel = "Confirmar", danger, onConfirm, onCancel }: ConfirmDialogProps) {
  return <Modal open={open} title={title} description="A ação será persistida somente neste navegador demonstrativo." onClose={onCancel} footer={<><Button variant="outline" onClick={onCancel}>Cancelar</Button><Button variant={danger ? "danger" : "default"} onClick={onConfirm}>{confirmLabel}</Button></>}>
    <div className="flex gap-3 rounded-xl border border-amber-400/20 bg-amber-400/10 p-4 text-sm"><AlertCircle className="mt-0.5 size-5 shrink-0 text-amber-400" /><p>{description}</p></div>
  </Modal>;
}
