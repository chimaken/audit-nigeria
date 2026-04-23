"use client";

import type { ElectionRace } from "@/lib/types";
import { cn } from "@/lib/utils";
import { electionRaceFromSearchParams } from "@/lib/election-race";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

const ACTIVE: { id: ElectionRace; label: string; hint: string }[] = [
  {
    id: "presidency",
    label: "Presidency",
    hint: "National presidential-style rollups (verified uploads)",
  },
  {
    id: "senate",
    label: "Senatorial",
    hint: "Lagos senatorial pilot from LGA rollups; other districts TBD",
  },
];

const COMING_SOON: { id: string; label: string }[] = [
  { id: "reps", label: "House of Reps" },
  { id: "gov", label: "Governorship" },
  { id: "hoa", label: "State Assembly" },
];

export function ElectionToggle() {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();
  const value = electionRaceFromSearchParams(sp);

  function setRace(next: ElectionRace) {
    const n = new URLSearchParams(sp.toString());
    n.delete("view");
    if (next === "senate") {
      n.set("race", "senate");
    } else {
      n.delete("race");
    }
    const q = n.toString();
    router.replace(q ? `${pathname}?${q}` : pathname);
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-3">
        <span className="text-xs font-medium uppercase tracking-wider text-slate-500">Office</span>
        <div className="inline-flex flex-wrap rounded-lg border border-slate-700 bg-slate-900/60 p-1">
          {ACTIVE.map((opt) => (
            <button
              key={opt.id}
              type="button"
              onClick={() => setRace(opt.id)}
              title={opt.hint}
              className={cn(
                "rounded-md px-3 py-1.5 text-sm font-medium transition-all",
                value === opt.id
                  ? "bg-emerald-600/90 text-white shadow"
                  : "text-slate-400 hover:text-slate-200",
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-[10px] uppercase tracking-wider text-slate-600">TBD</span>
        {COMING_SOON.map((opt) => (
          <button
            key={opt.id}
            type="button"
            disabled
            title="Date TBD"
            className="cursor-not-allowed rounded border border-slate-800/80 bg-slate-900/30 px-2 py-0.5 text-[11px] text-slate-600"
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  );
}
