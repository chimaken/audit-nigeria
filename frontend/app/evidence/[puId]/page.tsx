"use client";

import { CommandShell } from "@/components/layout/command-shell";
import { ProofGallery } from "@/components/evidence/proof-gallery";
import { fetchPu } from "@/lib/api";
import { DEFAULT_ELECTION_ID } from "@/lib/config";
import { electionRaceFromSearchParams } from "@/lib/election-race";
import { electionQueryString, electionStateIdFromSearchParam } from "@/lib/url-state";
import { consensusReviewReasonLabel, consensusStatusLabel } from "@/lib/election-labels";
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
  const puIdFromPath = Number(params.puId);
  const puIdFromQuery = Number(sp.get("pu_id"));
  const puId =
    Number.isFinite(puIdFromQuery) && puIdFromQuery > 0 ? puIdFromQuery : puIdFromPath;
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
    { href: `/${qLoading}`, label: "Home" },
    { label: `Polling unit ${puId}` },
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
  const mathEval = consensus?.math_evaluation as
    | {
        ok?: boolean;
        reason?: string | null;
        sum_party_votes?: number;
        total_valid?: number | null;
        rejected?: number | null;
        total_cast?: number | null;
      }
    | undefined;
  const summary = consensus?.summary as Record<string, number> | undefined;

  const crumbDynamic = [
    { href: `/${q}`, label: "Home" },
    { href: `/state/${d.state_id}${q}`, label: d.state_name || "State" },
    { href: `/state/${d.state_id}/lga/0${q}${q ? "&" : "?"}lga_id=${d.lga_id}`, label: d.lga_name },
    { label: d.pu_name },
  ];

  const rows = Object.entries(d.party_results)
    .filter(([, v]) => v > 0)
    .sort((a, b) => b[1] - a[1]);

  return (
    <CommandShell electionId={electionId} crumbs={crumbDynamic}>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {d.collation_source === "manual_correction" ? (
          <Badge variant="success" className="border border-emerald-700/60">
            Collation after manual review
          </Badge>
        ) : null}
        <Badge
          variant={d.consensus_status === "VERIFIED" ? "success" : d.consensus_status === "DISPUTED" ? "warn" : "muted"}
        >
          {consensusStatusLabel(d.consensus_status)}
        </Badge>
        {typeof d.confidence_score === "number" ? (
          <Badge variant="muted">Match strength {(d.confidence_score * 100).toFixed(0)}%</Badge>
        ) : null}
        <Badge variant={mathOk ? "success" : "warn"}>
          {mathOk ? "Sheet totals cross-checked" : "Sheet totals inconsistent"}
        </Badge>
      </div>
      {d.consensus_status === "DISPUTED" &&
      (d.review_reason || (d.review_errors && d.review_errors.length > 0)) ? (
        <div className="mb-4 rounded-md border border-slate-700/80 bg-slate-900/60 px-3 py-2 text-sm text-slate-200">
          <p className="font-medium text-slate-100">Why this needs review</p>
          <p className="mt-1 text-slate-300">{consensusReviewReasonLabel(d.review_reason)}</p>
          {d.review_errors && d.review_errors.length > 0 ? (
            <ul className="mt-2 max-h-32 list-inside list-disc overflow-y-auto font-mono text-xs text-slate-400">
              {d.review_errors.slice(0, 8).map((e, i) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
          ) : null}
          {typeof d.confidence_score === "number" && d.confidence_score === 0 ? (
            <p className="mt-2 text-xs text-slate-500">
              Match strength 0% usually means fewer than two successful reads, or every read failed—see
              errors above if listed.
            </p>
          ) : null}
        </div>
      ) : null}
      {!mathOk && (mathEval?.reason || mathEval?.sum_party_votes != null) ? (
        <p className="mb-4 rounded-md border border-amber-900/50 bg-amber-950/25 px-3 py-2 text-sm text-amber-100/95">
          <span className="font-medium">Arithmetic check: </span>
          {mathEval?.reason
            ? mathEval.reason
            : "Party columns and totals row do not match INEC-style rules (sum of valid votes = total valid; total valid + rejected = total cast)."}
        </p>
      ) : null}
      {d.ai_detected_location_line ? (
        <p className="mb-4 text-sm text-emerald-400/90">{d.ai_detected_location_line}</p>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <motion.div initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }}>
          <Card className="h-full">
            <CardHeader>
              <CardTitle>Votes from the sheet</CardTitle>
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
                        <span className="text-xs text-emerald-500">ahead</span>
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
              <CardTitle>Uploaded photos</CardTitle>
              <p className="text-sm text-slate-500">Swipe or zoom to read the sheet.</p>
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
