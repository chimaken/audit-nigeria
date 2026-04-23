import { cn } from "@/lib/utils";
import type { HTMLAttributes } from "react";

export function Badge({
  className,
  variant = "default",
  ...props
}: HTMLAttributes<HTMLSpanElement> & { variant?: "default" | "success" | "warn" | "muted" }) {
  const v = {
    default: "bg-slate-700 text-slate-100 border-slate-500",
    success: "bg-emerald-950 text-emerald-300 border-emerald-700",
    warn: "bg-amber-950 text-amber-200 border-amber-700",
    muted: "bg-slate-800 text-slate-400 border-slate-700",
  }[variant];
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium",
        v,
        className,
      )}
      {...props}
    />
  );
}
