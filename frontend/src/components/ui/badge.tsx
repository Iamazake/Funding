import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

type BadgeProps = HTMLAttributes<HTMLDivElement> & {
  variant?: "default" | "outline" | "success" | "warning" | "danger" | "info" | "neutral";
};

function Badge({
  className,
  variant = "default",
  ...props
}: BadgeProps) {
  return (
    <div
      className={cn(
        "inline-flex w-fit items-center rounded-full px-2.5 py-0.5 text-xs font-semibold",
        variant === "default" && "bg-primary text-primary-foreground",
        variant === "outline" && "border border-border text-foreground",
        variant === "success" && "border border-emerald-400/20 bg-emerald-400/10 text-emerald-400",
        variant === "warning" && "border border-amber-400/20 bg-amber-400/10 text-amber-400",
        variant === "danger" && "border border-rose-400/20 bg-rose-400/10 text-rose-400",
        variant === "info" && "border border-sky-400/20 bg-sky-400/10 text-sky-400",
        variant === "neutral" && "border border-border bg-muted text-muted-foreground",
        className,
      )}
      {...props}
    />
  );
}

export { Badge };
