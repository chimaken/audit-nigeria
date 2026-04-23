"use client";

import { CommandShell } from "@/components/layout/command-shell";
import { ProofGallery } from "@/components/evidence/proof-gallery";
import { fetchPu } from "@/lib/api";
import { DEFAULT_ELECTION_ID } from "@/lib/config";
import { electionRaceFromSearchParams } from "@/lib/election-race";
import { electionQueryString, electionStateIdFromSearchParam } from "@/lib/url-state";
import { partyColor, leadingParty } from "@/lib/party-colors";
import { useQuery } from "@tanstack/react-query";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { motion } from "framer-motion";

function EvidenceBody() {
  const params = useParams();
  const sp = useSearchParams();
  const puId = Number(params.puId);
  const electionId = Number(sp.get("election_id") ?? DEFAULT_ELECTION_ID);
  const race = electionRaceFromSearchParams(sp);
  const urlStateId = electionStateIdFromSearchParam(sp.get("state_id"));
  const qLoading = electionQueryString({
    electionId,
    race: race === "senate" ? "senate" : null,
    stateId: urlStateId,
  });

  const pu = useQuery({
    queryKey: ["pu", puId, electionId],
    queryFn: () => fetchPu(puId, electionId),
    refetchInterval: 12_000,
  });

  const crumbsLoading = [
    { href: `/${qLoading}`, label: "National" },
    { label: `PU ${puId}` },
  ];

  if (pu.isLoading) {
    return (
      <CommandShell electionId={electionId} crumbs={crumbsLoading}>
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="h-96 animate-pulse rounded-xl bg-slate-800/50" />
          <div className="h-96 animate-pulse rounded-xl bg-slate-800/50" />
        </div>
      </CommandShell>
    );
  }
  if (!pu.data) {
    return (
      <CommandShell electionId={electionId} crumbs={crumbsLoading}>
        <p className="text-amber-400">{String(pu.error)}</p>
      </CommandShell>
    );
  }

  const d = pu.data;
  const q = electionQueryString({
    electionId,
    race: race === "senate" ? "senate" : null,
    stateId: urlStateId ?? d.state_id,
  });
  const consensus = d.consensus as Record<string, unknown> | null;
  const mathOk = Boolean(consensus?.is_math_correct);
  const summary = consensus?.summary as Record<string, number> | undefined;

  const crumbDynamic = [
    { href: `/${q}`, label: "National" },
    { href: `/state/${d.state_id}${q}`, label: d.state_name || "State" },
    { href: `/state/${d.state_id}/lga/${d.lga_id}${q}`, label: d.lga_name },
    { label: d.pu_name },
  ];

  const rows = Object.entries(d.party_results)
    .filter(([, v]) => v > 0)
    .sort((a, b) => b[1] - a[1]);

  return (
    <CommandShell electionId={electionId} crumbs={crumbDynamic}>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Badge
          variant={d.consensus_status === "VERIFIED" ? "success" : d.consensus_status === "DISPUTED" ? "warn" : "muted"}
        >
          {d.consensus_status}
        </Badge>
        {typeof d.confidence_score === "number" ? (
          <Badge variant="muted">Confidence {(d.confidence_score * 100).toFixed(0)}%</Badge>
        ) : null}
        <Badge variant={mathOk ? "success" : "warn"}>{mathOk ? "Math consistent" : "Math check"}</Badge>
      </div>
      {d.ai_detected_location_line ? (
        <p className="mb-4 text-sm text-emerald-400/90">{d.ai_detected_location_line}</p>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <motion.div initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }}>
          <Card className="h-full">
            <CardHeader>
              <CardTitle>AI extraction — party totals</CardTitle>
              <p className="font-mono text-xs text-slate-500">{d.pu_code}</p>
            </CardHeader>
            <CardContent className="space-y-4">
              {summary ? (
                <div className="grid grid-cols-3 gap-2 text-center text-sm">
                  <div className="rounded border border-slate-800 p-2">
                    <div className="text-xs text-slate-500">Valid</div>
                    <div className="font-mono text-lg text-slate-100">{summary.total_valid}</div>
                  </div>
                  <div className="rounded border border-slate-800 p-2">
                    <div className="text-xs text-slate-500">Rejected</div>
                    <div className="font-mono text-lg text-slate-100">{summary.rejected}</div>
                  </div>
                  <div className="rounded border border-slate-800 p-2">
                    <div className="text-xs text-slate-500">Cast</div>
                    <div className="font-mono text-lg text-slate-100">{summary.total_cast}</div>
                  </div>
                </div>
              ) : null}
              <div className="space-y-1">
                {rows.map(([party, votes]) => (
                  <div
                    key={party}
                    className="flex items-center justify-between rounded-md border border-slate-800/80 bg-slate-900/50 px-2 py-1.5"
                  >
                    <span className="flex items-center gap-2 text-sm font-medium">
                      <span
                        className="h-2 w-2 rounded-full"
                        style={{ backgroundColor: partyColor(party) }}
                      />
                      {party}
                      {party === leadingParty(d.party_results) ? (
                        <span className="text-xs text-emerald-500">lead</span>
                      ) : null}
                    </span>
                    <span className="font-mono text-sm tabular-nums">{votes}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </motion.div>

        <motion.div initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }}>
          <Card className="h-full">
            <CardHeader>
              <CardTitle>Proof gallery</CardTitle>
              <p className="text-sm text-slate-500">Swipe / arrows · pinch-zoom the EC8A sheet</p>
            </CardHeader>
            <CardContent>
              <ProofGallery images={d.proof_images} />
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </CommandShell>
  );
}

export default function EvidencePage() {
  return (
    <Suspense fallback={<div className="p-10 text-center text-slate-500">Loading evidence…</div>}>
      <EvidenceBody />
    </Suspense>
  );
}
