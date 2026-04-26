import { Download } from "lucide-react";
import { cn } from "@/lib/utils";

/** Serves from `public/sample-data/` after static export (replace file to ship your real iRev extract). */
export const IREV_SAMPLE_DATA_PATH = "/sample-data/irev-previous-election-sample.zip" as const;
const DOWNLOAD_NAME = "irev-previous-election-sample.zip";

type Props = {
  variant?: "card" | "inline";
  className?: string;
};

export function IrevSampleDownloadCta({ variant = "card", className }: Props) {
  const text = (
    <div className="min-w-0 flex-1 space-y-1">
      <p className="text-sm font-medium text-slate-100">Reference: iRev (last election)</p>
      <p className="text-xs leading-relaxed text-slate-500">
        Collated from INEC iRev (previous election) — use to compare with the totals on this site.
      </p>
    </div>
  );

  const link = (
    <a
      href={IREV_SAMPLE_DATA_PATH}
      download={DOWNLOAD_NAME}
      className="inline-flex shrink-0 items-center justify-center gap-2 rounded-md border border-emerald-800/80 bg-emerald-950/50 px-4 py-2 text-sm font-medium text-emerald-200 transition-colors hover:border-emerald-600 hover:bg-emerald-900/50"
    >
      <Download className="h-4 w-4" aria-hidden />
      Download sample ZIP
    </a>
  );

  if (variant === "inline") {
    return (
      <div className={cn("flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-4", className)}>
        {text}
        {link}
      </div>
    );
  }

  return (
    <div
      className={cn(
        "flex flex-col gap-3 rounded-lg border border-slate-700/80 bg-slate-950/50 px-4 py-3 sm:flex-row sm:items-center sm:justify-between",
        className,
      )}
    >
      {text}
      {link}
    </div>
  );
}
