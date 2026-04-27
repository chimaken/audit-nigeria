"use client";

import { CommandShell } from "@/components/layout/command-shell";
import { NationalLeaderboard } from "@/components/dashboard/national-leaderboard";
import { SenatorialPilotBoard } from "@/components/dashboard/senatorial-pilot-board";
import { LgaVerificationMap } from "@/components/map/lga-verification-map";
import { IrevSampleDownloadCta } from "@/components/dashboard/irev-sample-download-cta";
import { ApiConnectionBanner } from "@/components/layout/api-connection-banner";
import { fetchNational, fetchState, fetchStates } from "@/lib/api";
import { DEFAULT_ELECTION_ID, DEFAULT_STATE_ID } from "@/lib/config";
import { electionRaceFromSearchParams } from "@/lib/election-race";
import { electionQueryString, electionStateIdFromSearchParam } from "@/lib/url-state";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { motion } from "framer-motion";
import type { StateListItem } from "@/lib/types";

export default function HomeClient() {
  const sp = useSearchParams();
  const pathname = usePathname() ?? "/";
  const router = useRouter();
  const electionId = Number(sp.get("election_id") ?? DEFAULT_ELECTION_ID);
  const race = electionRaceFromSearchParams(sp);
  const stateId = electionStateIdFromSearchParam(sp.get("state_id"));

  const q = electionQueryString({
    electionId,
    race: race === "senate" ? "senate" : null,
    stateId,
  });

  const states = useQuery<StateListItem[]>({
    queryKey: ["states"],
    queryFn: fetchStates,
    staleTime: 60_000,
  });

  const national = useQuery({
    queryKey: ["national", electionId],
    queryFn: () => fetchNational(electionId),
    refetchInterval: 15_000,
  });

  const lagosSenateRollup = useQuery({
    queryKey: ["state", 1, electionId, "senate-pilot"],
    queryFn: () => fetchState(1, electionId),
    enabled: race === "senate",
    refetchInterval: 15_000,
  });

  const stateDrilldown = useQuery({
    queryKey: ["state", stateId, electionId],
    queryFn: () => fetchState(stateId!, electionId),
    enabled: stateId != null && stateId >= 1,
    refetchInterval: 15_000,
  });

  function onStateChange(value: string) {
    const n = new URLSearchParams(sp.toString());
    if (value === "") {
      n.delete("state_id");
    } else {
      n.set("state_id", value);
    }
    const qs = n.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname);
  }

  const stateName =
    stateId == null
      ? "Nigeria"
      : (stateDrilldown.data?.state_name ??
        states.data?.find((s) => s.state_id === stateId)?.state_name ??
        `State ${stateId}`);

  const isLagos = stateId === DEFAULT_STATE_ID;
  const crumbs = [{ href: "/" + q, label: "Home" }];

  const blockingError = states.error ?? national.error ?? lagosSenateRollup.error;
  const showConnectionHelp =
    Boolean(blockingError) && (states.isError || national.isError || lagosSenateRollup.isError);

  return (
    <CommandShell electionId={electionId} crumbs={crumbs}>
      {showConnectionHelp ? <ApiConnectionBanner error={blockingError} /> : null}
      <IrevSampleDownloadCta className="mb-6" />
      <div key={race} className="grid gap-6 lg:grid-cols-2">
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <Card className="h-full">
            <CardHeader>
              <CardTitle>
                {race === "senate" ? "Senatorial (Lagos first)" : "Presidential — nationwide"}
              </CardTitle>
              <p className="text-sm text-slate-500">
                {race === "senate"
                  ? "Lagos is shown by senatorial district. More states will appear as results are added."
                  : "Nationwide totals from polling-unit sheets. Stronger checks apply when more than one photo is available for a unit."}
              </p>
            </CardHeader>
            <CardContent>
              {race === "presidency" ? (
                national.isLoading ? (
                  <div className="h-48 animate-pulse rounded-lg bg-slate-800/60" />
                ) : national.data ? (
                  <NationalLeaderboard
                    partyResults={national.data.party_results}
                    updatedAt={national.data.updated_at}
                    heading="Presidential — nationwide"
                    includesProvisionalDisputed={
                      Boolean(national.data.includes_provisional_disputed)
                    }
                  />
                ) : (
                  <p className="text-sm text-amber-400">
                    {showConnectionHelp ? "See the note above about your connection." : String(national.error)}
                  </p>
                )
              ) : lagosSenateRollup.isLoading ? (
                <div className="h-48 animate-pulse rounded-lg bg-slate-800/60" />
              ) : lagosSenateRollup.data ? (
                <SenatorialPilotBoard lgas={lagosSenateRollup.data.lgas} />
              ) : (
                <p className="text-sm text-amber-400">
                  {showConnectionHelp ? "See the note above about your connection." : String(lagosSenateRollup.error)}
                </p>
              )}
              <div className="mt-4 flex justify-center border-t border-slate-800/80 pt-4">
                <Link
                  href={`/upload${q}`}
                  className="text-sm font-medium text-emerald-500/90 hover:text-emerald-400 hover:underline"
                >
                  Upload a result sheet (EC8A)
                </Link>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}>
          <Card>
            <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0 flex-1">
                <CardTitle>Map</CardTitle>
                <p className="text-sm text-slate-500">
                  {race === "senate"
                    ? "Pick a state to explore. Switch to President above for nationwide totals."
                    : stateId == null
                      ? "One marker per state. Pick a state below to see local government areas."
                      : "Each area is coloured by who is ahead there. Darker means more complete results."}
                </p>
                <p className="mt-1 text-xs text-slate-600">Focus: {stateName}</p>
              </div>
              <label className="flex shrink-0 items-center gap-2 text-sm text-slate-400">
                State
                <select
                  className="max-w-[14rem] rounded-md border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm text-slate-200"
                  value={stateId != null ? String(stateId) : ""}
                  disabled={!states.data?.length}
                  onChange={(e) => onStateChange(e.target.value)}
                >
                  <option value="">Nigeria (overview)</option>
                  {states.data?.map((s) => (
                    <option key={s.state_id} value={s.state_id}>
                      {s.state_name}
                    </option>
                  )) ?? null}
                </select>
              </label>
            </CardHeader>
            <CardContent>
              {stateId == null ? (
                <LgaVerificationMap mode="national" />
              ) : stateDrilldown.isLoading ? (
                <div className="h-64 animate-pulse rounded-lg bg-slate-800/60" />
              ) : stateDrilldown.data ? (
                <LgaVerificationMap
                  mode="state"
                  stateName={stateDrilldown.data.state_name}
                  lgas={stateDrilldown.data.lgas}
                />
              ) : (
                <p className="text-sm text-amber-400">
                  {String(stateDrilldown.error ?? "Could not load state drill-down.")}
                </p>
              )}
              {stateId != null && stateDrilldown.data ? (
                <div className="mt-4 flex max-h-48 flex-col gap-2 overflow-y-auto text-sm">
                  <p className="text-xs text-slate-500">LGAs (links)</p>
                  <ul className="space-y-1 text-slate-300">
                    {stateDrilldown.data.lgas.map((l) => (
                      <li key={l.lga_id}>
                        <Link
                          href={`/state/${stateId}/lga/${l.lga_id}${q}`}
                          className="block rounded-md border border-slate-800 bg-slate-900/40 px-2 py-1 hover:border-emerald-800 hover:text-emerald-200"
                        >
                          {l.lga_name}
                        </Link>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              <div className="mt-4 flex flex-wrap gap-2 text-sm">
                {stateId != null ? (
                  <>
                    <Link
                      href={`/state/${stateId}${q}`}
                      className="rounded-md border border-emerald-800 bg-emerald-950/40 px-3 py-1.5 text-emerald-200 hover:bg-emerald-900/50"
                    >
                      Open {stateName}
                    </Link>
                    {isLagos ? (
                      <Link
                        href={`/state/${stateId}/lga/11${q}`}
                        className="rounded-md border border-slate-700 px-3 py-1.5 text-slate-300 hover:border-emerald-700 hover:text-emerald-200"
                      >
                        Ikeja area
                      </Link>
                    ) : null}
                  </>
                ) : null}
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </div>

    </CommandShell>
  );
}
