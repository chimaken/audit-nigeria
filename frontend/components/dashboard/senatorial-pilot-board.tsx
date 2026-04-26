"use client";

import { NationalLeaderboard } from "@/components/dashboard/national-leaderboard";
import { SENATE_ORDER, lagosSenateDistrictRollups } from "@/lib/lagos-senatorial";
import type { LgaRow } from "@/lib/types";
import { useMemo } from "react";

export function SenatorialPilotBoard({ lgas }: { lgas: LgaRow[] }) {
  const rollups = useMemo(() => lagosSenateDistrictRollups(lgas), [lgas]);

  return (
    <div className="space-y-5">
      <p className="text-xs leading-relaxed text-slate-500">
        Lagos is grouped into three senate districts. Other states will be added over time.
      </p>
      <div className="grid gap-4 md:grid-cols-3">
        {SENATE_ORDER.map((district) => {
          const { parties, updatedAt } = rollups[district];
          return (
            <div
              key={district}
              className="rounded-lg border border-slate-800/90 bg-slate-950/40 p-3 ring-1 ring-slate-800/60"
            >
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-emerald-400/95">{district}</h4>
              <NationalLeaderboard partyResults={parties} updatedAt={updatedAt} heading="Votes" />
            </div>
          );
        })}
      </div>
    </div>
  );
}
