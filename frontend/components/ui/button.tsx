import { cn } from "@/lib/utils";
import type { ButtonHTMLAttributes } from "react";

export function Button({
  className,
  variant = "default",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "default" | "ghost" | "outline" | "accent";
}) {
  const variants: Record<string, string> = {
    default: "bg-slate-800 text-slate-100 hover:bg-slate-700 border border-slate-600",
    ghost: "bg-transparent hover:bg-slate-800/80 text-slate-200",
    outline: "border border-slate-600 bg-transparent hover:bg-slate-800/60",
    accent: "bg-emerald-600 text-white hover:bg-emerald-500 border border-emerald-500",
  };
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center rounded-md px-3 py-2 text-sm font-medium transition-colors disabled:opacity-50",
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}
