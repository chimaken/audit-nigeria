"use client";

import { CommandShell } from "@/components/layout/command-shell";
import { LgaVerificationMap } from "@/components/map/lga-verification-map";
import { fetchState } from "@/lib/api";
import { DEFAULT_ELECTION_ID } from "@/lib/config";
import { electionRaceFromSearchParams } from "@/lib/election-race";
import { electionQueryString } from "@/lib/url-state";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { motion } from "framer-motion";
import { leadingParty } from "@/lib/party-colors";
import { SENATE_ORDER, senateDistrictForLga } from "@/lib/lagos-senatorial";

function StateBody() {
  const params = useParams();
  const sp = useSearchParams();
  const stateId = Number(params.stateId);
  const electionId = Number(sp.get("election_id") ?? DEFAULT_ELECTION_ID);
  const race = electionRaceFromSearchParams(sp);
  const q = electionQueryString({
    electionId,
    race: race === "senate" ? "senate" : null,
    stateId,
  });

  const state = useQuery({
    queryKey: ["state", stateId, electionId],
    queryFn: () => fetchState(stateId, electionId),
    refetchInterval: 15_000,
  });

  const crumbFixed = [
    { href: `/${q}`, label: "Home" },
    { label: state.data?.state_name ?? `State ${stateId}` },
  ];

  if (state.isLoading) {
    return (
      <CommandShell electionId={electionId} crumbs={crumbFixed}>
        <div className="h-96 animate-pulse rounded-xl bg-slate-800/50" />
      </CommandShell>
    );
  }
  if (!state.data) {
    return (
      <CommandShell electionId={electionId} crumbs={crumbFixed}>
        <p className="text-amber-400">{String(state.error)}</p>
      </CommandShell>
    );
  }

  const d = state.data;

  return (
    <CommandShell electionId={electionId} crumbs={crumbFixed}>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <motion.h1
            className="text-2xl font-bold text-slate-50"
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
          >
            {d.state_name}
          </motion.h1>
          <p className="text-sm text-slate-500">Live totals by area</p>
        </div>
        {leadingParty(d.state_party_results) ? (
          <Badge variant="success">Ahead in this state: {leadingParty(d.state_party_results)}</Badge>
        ) : null}
      </div>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Map of local areas</CardTitle>
        </CardHeader>
        <CardContent>
          <LgaVerificationMap mode="state" stateName={d.state_name} lgas={d.lgas} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Local government areas</CardTitle>
        </CardHeader>
        <CardContent>
          {race === "senate" && stateId === 1 ? (
            <div className="grid gap-6 md:grid-cols-3">
              {SENATE_ORDER.map((district) => (
                <div key={district}>
                  <h3 className="mb-2 text-sm font-semibold text-emerald-400">{district}</h3>
                  <ul className="space-y-2">
                    {d.lgas
                      .filter((l) => senateDistrictForLga(l.lga_name) === district)
                      .map((l) => (
                        <li key={l.lga_id}>
                          <Link
                            href={`/state/${stateId}/lga/0${q}${q ? "&" : "?"}lga_id=${l.lga_id}`}
                            className="flex flex-col rounded-lg border border-slate-800 bg-slate-900/40 p-2 hover:border-emerald-800"
                          >
                            <span className="font-medium text-slate-100">{l.lga_name}</span>
                            <span className="text-xs text-slate-500">
                              {l.updated_at ? "Has totals" : "Waiting for sheets"}
                            </span>
                          </Link>
                        </li>
                      ))}
                  </ul>
                </div>
              ))}
            </div>
          ) : (
            <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {d.lgas.map((l) => (
                <li key={l.lga_id}>
                  <Link
                    href={`/state/${stateId}/lga/0${q}${q ? "&" : "?"}lga_id=${l.lga_id}`}
                    className="flex flex-col rounded-lg border border-slate-800 bg-slate-900/40 p-3 hover:border-emerald-800"
                  >
                    <span className="font-medium text-slate-100">{l.lga_name}</span>
                    <span className="text-xs text-slate-500">
                      {l.updated_at ? "Has totals" : "No totals yet"}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </CommandShell>
  );
}

export default function StatePage() {
  return (
    <Suspense fallback={<div className="p-10 text-center text-slate-500">Loading state…</div>}>
      <StateBody />
    </Suspense>
  );
}
