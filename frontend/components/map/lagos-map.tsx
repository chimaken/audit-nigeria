"use client";

import dynamic from "next/dynamic";
import type { LgaRow } from "@/lib/types";

const Inner = dynamic(() => import("./lagos-map-inner"), {
  ssr: false,
  loading: () => (
    <div className="flex h-[min(420px,55vh)] w-full items-center justify-center rounded-lg border border-command-border bg-command-panel text-sm text-slate-500">
      Loading map…
    </div>
  ),
});

export function LagosMap({
  lgas,
  focusLgaId,
}: {
  lgas: LgaRow[];
  focusLgaId?: number | null;
}) {
  return <Inner lgas={lgas} focusLgaId={focusLgaId} />;
}
