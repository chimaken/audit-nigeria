"use client";

import { partyColor, leadingParty } from "@/lib/party-colors";
import type { PartyResults } from "@/lib/types";
import { motion } from "framer-motion";
import { Badge } from "@/components/ui/badge";

export function NationalLeaderboard({
  partyResults,
  updatedAt,
  heading = "National leaderboard",
  includesProvisionalDisputed = false,
}: {
  partyResults: PartyResults;
  updatedAt: string | null;
  heading?: string;
  /** When true, totals include best-effort figures from disputed units (not only 2-of-3 verified). */
  includesProvisionalDisputed?: boolean;
}) {
  const rows = Object.entries(partyResults)
    .filter(([, v]) => v > 0)
    .sort((a, b) => b[1] - a[1]);

  const lead = leadingParty(partyResults);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400">{heading}</h3>
        <div className="flex flex-wrap items-center gap-2">
          {includesProvisionalDisputed ? (
            <Badge variant="warn">Includes units under review</Badge>
          ) : null}
          {lead ? (
            <Badge variant="success" className="gap-1">
              Leading: <span style={{ color: partyColor(lead) }}>{lead}</span>
            </Badge>
          ) : (
            <Badge variant="muted">No totals yet</Badge>
          )}
        </div>
      </div>
      {updatedAt ? (
        <p className="text-xs text-slate-500">Updated {new Date(updatedAt).toLocaleString()}</p>
      ) : null}
      <div className="max-h-72 space-y-1 overflow-y-auto pr-1">
        {rows.length === 0 ? (
          <p className="text-sm text-slate-500">Upload result sheets to see totals appear.</p>
        ) : (
          rows.map(([party, votes], i) => (
            <motion.div
              key={party}
              initial={{ opacity: 0, x: -6 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.02 }}
              className="flex items-center gap-3 rounded-lg border border-slate-800 bg-slate-900/50 px-3 py-2"
            >
              <span
                className="h-2 w-2 shrink-0 rounded-full"
                style={{ backgroundColor: partyColor(party) }}
              />
              <span className="w-10 font-mono text-sm font-semibold text-slate-200">{party}</span>
              <div className="flex-1">
                <div className="h-1.5 overflow-hidden rounded-full bg-slate-800">
                  <motion.div
                    className="h-full rounded-full"
                    style={{ backgroundColor: partyColor(party) }}
                    initial={{ width: 0 }}
                    animate={{
                      width: `${Math.min(100, (votes / (rows[0]?.[1] || 1)) * 100)}%`,
                    }}
                    transition={{ type: "spring", stiffness: 120, damping: 20 }}
                  />
                </div>
              </div>
              <span className="font-mono text-sm tabular-nums text-slate-100">{votes.toLocaleString()}</span>
            </motion.div>
          ))
        )}
      </div>
    </div>
  );
}
