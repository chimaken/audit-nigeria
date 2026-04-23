"use client";

import dynamic from "next/dynamic";
import type { LgaVerificationMapInnerProps } from "./lga-verification-map-inner";

const Inner = dynamic(() => import("./lga-verification-map-inner"), {
  ssr: false,
  loading: () => (
    <div className="flex h-[min(420px,55vh)] w-full items-center justify-center rounded-lg border border-command-border bg-command-panel text-sm text-slate-500">
      Loading map…
    </div>
  ),
});

export function LgaVerificationMap(props: LgaVerificationMapInnerProps) {
  return <Inner {...props} />;
}
