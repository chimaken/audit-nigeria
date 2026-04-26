"use client";

import { IrevSampleDownloadCta } from "@/components/dashboard/irev-sample-download-cta";
import { CommandShell } from "@/components/layout/command-shell";
import {
  clientAsyncUploadPreferred,
  fetchHealth,
  resetCollatedVotes,
  type SheetUploadProgress,
  uploadResultSheet,
  uploadResultSheetAsync,
} from "@/lib/api";
import { DEFAULT_ELECTION_ID } from "@/lib/config";
import { electionRaceFromSearchParams } from "@/lib/election-race";
import { electionQueryString, electionStateIdFromSearchParam } from "@/lib/url-state";
import type { SheetUploadResponse } from "@/lib/types";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { motion } from "framer-motion";

export default function UploadClient() {
  const sp = useSearchParams();
  const electionId = Number(sp.get("election_id") ?? DEFAULT_ELECTION_ID);
  const race = electionRaceFromSearchParams(sp);
  const stateId = electionStateIdFromSearchParam(sp.get("state_id"));
  const q = electionQueryString({
    electionId,
    race: race === "senate" ? "senate" : null,
    stateId,
  });

  const [puIdRaw, setPuIdRaw] = useState("");
  const [metadata, setMetadata] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<SheetUploadProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<SheetUploadResponse | null>(null);
  /** From GET /health: server has no OpenRouter key — pu_id is required for upload. */
  const [uploadRequiresPuId, setUploadRequiresPuId] = useState(false);
  /** From GET /health; also refreshed on each submit so we never POST /upload before knowing async is available. */
  const [useAsyncUploadPath, setUseAsyncUploadPath] = useState(false);
  /** Initial /health failed (e.g. wrong NEXT_PUBLIC_API_URL in static export). */
  const [healthWarn, setHealthWarn] = useState<string | null>(null);
  /** From GET /health: DASHBOARD_RESET_TOKEN set — show reset collated votes CTA. */
  const [resetCollatedVotesEnabled, setResetCollatedVotesEnabled] = useState(false);
  const [resetToken, setResetToken] = useState("");
  const [resetBusy, setResetBusy] = useState(false);
  const [resetMsg, setResetMsg] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchHealth()
      .then((h) => {
        if (cancelled) {
          return;
        }
        if (h.openrouter_configured === false) {
          setUploadRequiresPuId(true);
        }
        if (h.reset_collated_votes_enabled === true) {
          setResetCollatedVotesEnabled(true);
        }
        if (h.async_upload_enabled === true && clientAsyncUploadPreferred()) {
          setUseAsyncUploadPath(true);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setHealthWarn(
            err instanceof Error ? err.message : "Could not reach the results service. Check your connection.",
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const onSubmit = useCallback(
    async (e: FormEvent) => {
      e.preventDefault();
      setError(null);
      setDone(null);
      if (!file) {
        setError("Please choose a clear photo of the result sheet.");
        return;
      }
      const puParsed = puIdRaw.trim() ? Number(puIdRaw.trim()) : undefined;
      if (puIdRaw.trim() && (!Number.isFinite(puParsed) || puParsed! < 1)) {
        setError("Polling unit number must be a whole number greater than zero.");
        return;
      }
      setBusy(true);
      setUploadProgress({
        phase: "presign",
        message: "Connecting…",
        percent: null,
      });
      try {
        let health;
        try {
          health = await fetchHealth();
        } catch (he) {
          throw new Error(
            `Cannot reach the results service (${he instanceof Error ? he.message : String(he)}). Try again or check your connection.`,
          );
        }
        setUploadRequiresPuId(health.openrouter_configured === false);
        if (health.openrouter_configured === false && (puParsed == null || puParsed < 1)) {
          throw new Error(
            "Enter the polling unit number for this sheet, or ask your administrator to turn on automatic location reading.",
          );
        }
        const asyncPipeline =
          health.async_upload_enabled === true && clientAsyncUploadPreferred();
        setUseAsyncUploadPath(asyncPipeline);
        const res = asyncPipeline
          ? await uploadResultSheetAsync({
              electionId,
              file,
              puId: puParsed,
              metadata: metadata.trim() || null,
              onProgress: setUploadProgress,
            })
          : await uploadResultSheet({
              electionId,
              file,
              puId: puParsed,
              metadata: metadata.trim() || null,
              onProgress: setUploadProgress,
            });
        setDone(res);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setBusy(false);
        setUploadProgress(null);
      }
    },
    [electionId, file, metadata, puIdRaw, uploadRequiresPuId],
  );

  const onResetCollated = useCallback(async () => {
    setResetMsg(null);
    const tok = resetToken.trim();
    if (!tok) {
      setResetMsg("Enter the reset code first.");
      return;
    }
    if (
      !window.confirm(
        `Clear all uploaded sheets and totals for this election? You can upload again afterwards.`,
      )
    ) {
      return;
    }
    setResetBusy(true);
    try {
      const out = await resetCollatedVotes(electionId, tok);
      setResetMsg(
        `Reset OK: ${out.upload_rows_deleted} upload(s), ${out.cluster_rows_deleted} cluster(s), ` +
          `${out.proof_files_removed} file(s) removed; tallies cleared.`,
      );
      setDone(null);
    } catch (err) {
      setResetMsg(err instanceof Error ? err.message : String(err));
    } finally {
      setResetBusy(false);
    }
  }, [electionId, resetToken]);

  const crumbs = [
    { href: "/" + q, label: "Home" },
    { label: "Add a sheet" },
  ];

  const evidenceQ = electionQueryString({
    electionId,
    race: race === "senate" ? "senate" : null,
    stateId,
  });

  return (
    <CommandShell electionId={electionId} crumbs={crumbs}>
      <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
        <Card className="max-w-2xl">
          <CardHeader>
            <CardTitle>Add a result sheet</CardTitle>
            <p className="text-sm text-slate-500">
              {useAsyncUploadPath
                ? "Your photo is sent securely, then read in the background. You can leave this page once the bar finishes."
                : "Upload a clear photo of the official result sheet for this election. Reading the sheet may take a minute."}
            </p>
            <div className="mt-4">
              <IrevSampleDownloadCta variant="inline" />
            </div>
          </CardHeader>
          <CardContent>
            {uploadRequiresPuId ? (
              <p className="mb-4 rounded-md border border-amber-800/70 bg-amber-950/40 px-3 py-2 text-sm text-amber-100">
                <strong className="font-semibold">Enter the polling unit number below.</strong> Automatic reading of the
                sheet header is turned off on this deployment.
              </p>
            ) : null}
            {healthWarn ? (
              <p className="mb-4 rounded-md border border-amber-900/60 bg-amber-950/30 px-3 py-2 text-sm text-amber-200">
                {healthWarn}
              </p>
            ) : null}
            <form className="space-y-4" onSubmit={onSubmit}>
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-slate-300">Photo of result sheet</label>
                <Input
                  type="file"
                  accept="image/jpeg,image/png,image/webp,image/gif"
                  className="cursor-pointer file:mr-3 file:rounded file:border-0 file:bg-emerald-900/50 file:px-2 file:py-1 file:text-sm file:text-emerald-200"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-slate-300" htmlFor="pu_id">
                  Polling unit number{" "}
                  <span className="font-normal text-slate-500">
                    ({uploadRequiresPuId ? "required" : "optional if the header is readable"})
                  </span>
                </label>
                <Input
                  id="pu_id"
                  inputMode="numeric"
                  placeholder="Number from your organisers"
                  value={puIdRaw}
                  onChange={(e) => setPuIdRaw(e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-slate-300" htmlFor="metadata">
                  Extra details <span className="font-normal text-slate-500">(optional — organisers only)</span>
                </label>
                <textarea
                  id="metadata"
                  rows={3}
                  placeholder="Leave blank unless you were given a special format to paste here."
                  value={metadata}
                  onChange={(e) => setMetadata(e.target.value)}
                  className="w-full rounded-md border border-slate-600 bg-slate-900/80 px-3 py-2 font-mono text-xs text-slate-100 placeholder:text-slate-600 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-0 focus-visible:outline-emerald-500/60"
                />
              </div>
              {busy && uploadProgress ? (
                <div
                  className="space-y-2 rounded-lg border border-slate-600 bg-slate-900/90 px-4 py-3 shadow-lg ring-1 ring-emerald-900/30"
                  role="status"
                  aria-live="polite"
                  aria-busy="true"
                >
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-xs font-semibold uppercase tracking-wide text-emerald-400/90">
                      Please wait
                    </p>
                    {uploadProgress.percent != null ? (
                      <span className="font-mono text-xs text-slate-400">{uploadProgress.percent}%</span>
                    ) : (
                      <span className="text-xs text-slate-500">Working…</span>
                    )}
                  </div>
                  <p className="text-sm text-slate-200">{uploadProgress.message}</p>
                  <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-800">
                    {uploadProgress.percent != null ? (
                      <motion.div
                        className="h-full rounded-full bg-gradient-to-r from-emerald-700 to-emerald-500"
                        initial={{ width: 0 }}
                        animate={{ width: `${Math.min(100, uploadProgress.percent)}%` }}
                        transition={{ type: "spring", stiffness: 120, damping: 22 }}
                      />
                    ) : (
                      <div className="relative h-full w-full overflow-hidden rounded-full bg-slate-800">
                        <motion.div
                          className="absolute inset-y-0 w-2/5 rounded-full bg-gradient-to-r from-emerald-800/80 to-emerald-500/90"
                          animate={{ left: ["-40%", "100%"] }}
                          transition={{ duration: 1.35, repeat: Infinity, ease: "linear" }}
                        />
                      </div>
                    )}
                  </div>
                  <p className="text-xs text-slate-500">
                    {uploadProgress.phase === "direct_upload" ||
                    uploadProgress.phase === "direct_processing"
                      ? "Keep this tab open until the check finishes."
                      : "You can leave this page once the upload bar completes; the check continues in the background."}
                  </p>
                </div>
              ) : null}
              {error ? (
                <p className="rounded-md border border-amber-900/60 bg-amber-950/30 px-3 py-2 text-sm text-amber-200">
                  {error}
                </p>
              ) : null}
              {done ? (
                <div className="space-y-2 rounded-md border border-emerald-900/50 bg-emerald-950/20 px-3 py-3 text-sm text-emerald-100">
                  <p>
                    Saved for polling unit <span className="font-semibold text-emerald-100">{done.resolved_pu_id}</span>
                    .
                  </p>
                  {done.ai_detected_location_line ? (
                    <p className="text-emerald-200/90">{done.ai_detected_location_line}</p>
                  ) : null}
                  {done.ingestion_warnings?.length ? (
                    <p className="text-amber-200/90">Warnings: {done.ingestion_warnings.join(", ")}</p>
                  ) : null}
                  <Link
                    href={`/evidence/0${evidenceQ}${evidenceQ ? "&" : "?"}pu_id=${done.resolved_pu_id}`}
                    className="inline-block rounded-md border border-emerald-700 px-3 py-1.5 text-emerald-200 hover:bg-emerald-900/40"
                  >
                    View this polling unit →
                  </Link>
                </div>
              ) : null}
              <Button type="submit" disabled={busy} className="w-full sm:w-auto">
                {busy ? (useAsyncUploadPath ? "Sending…" : "Uploading…") : "Submit sheet"}
              </Button>
            </form>

            {resetCollatedVotesEnabled ? (
              <div className="mt-8 border-t border-slate-700 pt-6 space-y-3">
                <h3 className="text-sm font-semibold text-slate-200">Clear results (training only)</h3>
                <p className="text-xs text-slate-500">
                  Removes uploaded sheets and running totals for this election. Ward and polling-unit lists stay in
                  place.
                </p>
                <div className="space-y-1.5">
                  <label className="text-sm font-medium text-slate-300" htmlFor="reset_token">
                    Reset code from your technical team
                  </label>
                  <Input
                    id="reset_token"
                    type="password"
                    autoComplete="off"
                    placeholder="Paste reset code"
                    value={resetToken}
                    onChange={(e) => setResetToken(e.target.value)}
                    className="font-mono text-sm"
                  />
                </div>
                {resetMsg ? (
                  <p className="rounded-md border border-slate-600 bg-slate-900/60 px-3 py-2 text-xs text-slate-200">
                    {resetMsg}
                  </p>
                ) : null}
                <Button
                  type="button"
                  variant="outline"
                  disabled={resetBusy}
                  onClick={() => void onResetCollated()}
                  className="border-rose-900/70 text-rose-200 hover:bg-rose-950/40"
                >
                  {resetBusy ? "Clearing…" : "Clear all results for this election"}
                </Button>
              </div>
            ) : null}
          </CardContent>
        </Card>
      </motion.div>
    </CommandShell>
  );
}
