"use client";

import { CommandShell } from "@/components/layout/command-shell";
import { LgaVerificationMap } from "@/components/map/lga-verification-map";
import { fetchLga, fetchState } from "@/lib/api";
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

function LgaBody() {
  const params = useParams();
  const sp = useSearchParams();
  const stateId = Number(params.stateId);
  const lgaId = Number(params.lgaId);
  const electionId = Number(sp.get("election_id") ?? DEFAULT_ELECTION_ID);
  const race = electionRaceFromSearchParams(sp);
  const q = electionQueryString({
    electionId,
    race: race === "senate" ? "senate" : null,
    stateId,
  });

  const lga = useQuery({
    queryKey: ["lga", lgaId, electionId],
    queryFn: () => fetchLga(lgaId, electionId),
    refetchInterval: 12_000,
  });

  const state = useQuery({
    queryKey: ["state", stateId, electionId],
    queryFn: () => fetchState(stateId, electionId),
    enabled: stateId > 0,
  });

  const crumbs = [
    { href: `/${q}`, label: "National" },
    { href: `/state/${stateId}${q}`, label: state.data?.state_name ?? `State ${stateId}` },
    { label: lga.data?.lga_name ?? `LGA ${lgaId}` },
  ];

  if (lga.isLoading || state.isLoading) {
    return (
      <CommandShell electionId={electionId} crumbs={crumbs}>
        <div className="h-72 animate-pulse rounded-xl bg-slate-800/50" />
      </CommandShell>
    );
  }
  if (!lga.data) {
    return (
      <CommandShell electionId={electionId} crumbs={crumbs}>
        <p className="text-amber-400">{String(lga.error)}</p>
      </CommandShell>
    );
  }

  const d = lga.data;

  return (
    <CommandShell electionId={electionId} crumbs={crumbs}>
      <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="mb-6">
        <h1 className="text-2xl font-bold text-slate-50">{d.lga_name}</h1>
        <p className="text-sm text-slate-500">
          {state.data?.state_name} · Election #{electionId}
        </p>
      </motion.div>

      {state.data ? (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>Map focus — {d.lga_name}</CardTitle>
          </CardHeader>
          <CardContent>
            <LgaVerificationMap
              mode="state"
              stateName={state.data.state_name}
              lgas={state.data.lgas}
              focusLgaId={lgaId}
            />
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Polling units</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2">
            {d.polling_units.map((pu) => (
              <li key={pu.pu_id}>
                <Link
                  href={`/evidence/${pu.pu_id}${q}`}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-800 bg-slate-900/40 px-3 py-2 hover:border-emerald-800"
                >
                  <div>
                    <div className="font-medium text-slate-100">{pu.pu_name}</div>
                    <div className="font-mono text-xs text-slate-500">{pu.pu_code}</div>
                  </div>
                  <Badge
                    variant={
                      pu.consensus_status === "VERIFIED"
                        ? "success"
                        : pu.consensus_status === "DISPUTED"
                          ? "warn"
                          : "muted"
                    }
                  >
                    {pu.consensus_status}
                  </Badge>
                </Link>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </CommandShell>
  );
}

export default function LgaPage() {
  return (
    <Suspense fallback={<div className="p-10 text-center text-slate-500">Loading LGA…</div>}>
      <LgaBody />
    </Suspense>
  );
}
