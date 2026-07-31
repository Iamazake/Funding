import { X } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";

import { Button } from "@/components/ui/button";

interface ModalProps {
  open: boolean;
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
  onClose: () => void;
}

export function Modal({ open, title, description, children, footer, onClose }: ModalProps) {
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    closeButtonRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/75 p-4 backdrop-blur-sm" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="max-h-[90vh] w-full max-w-xl overflow-auto rounded-2xl border border-border bg-card shadow-2xl" role="dialog" aria-modal="true" aria-labelledby="modal-title">
        <header className="flex items-start justify-between gap-4 border-b border-border p-6">
          <div><h2 id="modal-title" className="text-xl font-semibold">{title}</h2>{description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}</div>
          <Button ref={closeButtonRef} size="icon" variant="ghost" onClick={onClose} aria-label="Fechar"><X className="size-4" /></Button>
        </header>
        <div className="p-6">{children}</div>
        {footer && <footer className="flex justify-end gap-3 border-t border-border p-6">{footer}</footer>}
      </section>
    </div>
  );
}
