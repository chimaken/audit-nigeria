"use client";

import { CommandShell } from "@/components/layout/command-shell";
import { uploadResultSheet } from "@/lib/api";
import { DEFAULT_ELECTION_ID } from "@/lib/config";
import { electionRaceFromSearchParams } from "@/lib/election-race";
import { electionQueryString, electionStateIdFromSearchParam } from "@/lib/url-state";
import type { SheetUploadResponse } from "@/lib/types";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useState, type FormEvent } from "react";
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
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<SheetUploadResponse | null>(null);

  const onSubmit = useCallback(
    async (e: FormEvent) => {
      e.preventDefault();
      setError(null);
      setDone(null);
      if (!file) {
        setError("Choose an image file (EC8A photo).");
        return;
      }
      const puParsed = puIdRaw.trim() ? Number(puIdRaw.trim()) : undefined;
      if (puIdRaw.trim() && (!Number.isFinite(puParsed) || puParsed! < 1)) {
        setError("Polling unit id must be a positive integer when provided.");
        return;
      }
      setBusy(true);
      try {
        const res = await uploadResultSheet({
          electionId,
          file,
          puId: puParsed,
          metadata: metadata.trim() || null,
        });
        setDone(res);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setBusy(false);
      }
    },
    [electionId, file, metadata, puIdRaw],
  );

  const crumbs = [
    { href: "/" + q, label: "National" },
    { label: "Upload evidence" },
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
            <CardTitle>Upload EC8A evidence</CardTitle>
            <p className="text-sm text-slate-500">
              Posts to <span className="font-mono text-slate-400">POST /upload</span> for election{" "}
              <span className="font-mono text-emerald-500/90">{electionId}</span>. If the API has no vision key, you
              must supply a known <span className="font-mono">pu_id</span>; otherwise leave it blank and the server
              resolves location from the form header.
            </p>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={onSubmit}>
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-slate-300">Result sheet image</label>
                <Input
                  type="file"
                  accept="image/jpeg,image/png,image/webp,image/gif"
                  className="cursor-pointer file:mr-3 file:rounded file:border-0 file:bg-emerald-900/50 file:px-2 file:py-1 file:text-sm file:text-emerald-200"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-slate-300" htmlFor="pu_id">
                  Polling unit id <span className="font-normal text-slate-500">(optional)</span>
                </label>
                <Input
                  id="pu_id"
                  inputMode="numeric"
                  placeholder="e.g. 42"
                  value={puIdRaw}
                  onChange={(e) => setPuIdRaw(e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-slate-300" htmlFor="metadata">
                  Metadata JSON <span className="font-normal text-slate-500">(optional)</span>
                </label>
                <textarea
                  id="metadata"
                  rows={4}
                  placeholder='{"gps": {"lat": 6.5, "lng": 3.3}}'
                  value={metadata}
                  onChange={(e) => setMetadata(e.target.value)}
                  className="w-full rounded-md border border-slate-600 bg-slate-900/80 px-3 py-2 font-mono text-xs text-slate-100 placeholder:text-slate-600 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-0 focus-visible:outline-emerald-500/60"
                />
              </div>
              {error ? (
                <p className="rounded-md border border-amber-900/60 bg-amber-950/30 px-3 py-2 text-sm text-amber-200">
                  {error}
                </p>
              ) : null}
              {done ? (
                <div className="space-y-2 rounded-md border border-emerald-900/50 bg-emerald-950/20 px-3 py-3 text-sm text-emerald-100">
                  <p>
                    Upload <span className="font-mono">#{done.upload_id}</span> stored for PU{" "}
                    <span className="font-mono">{done.resolved_pu_id}</span> (cluster{" "}
                    <span className="font-mono">{done.cluster_id}</span>).
                  </p>
                  {done.ai_detected_location_line ? (
                    <p className="text-emerald-200/90">{done.ai_detected_location_line}</p>
                  ) : null}
                  {done.ingestion_warnings?.length ? (
                    <p className="text-amber-200/90">Warnings: {done.ingestion_warnings.join(", ")}</p>
                  ) : null}
                  <Link
                    href={`/evidence/${done.resolved_pu_id}${evidenceQ}`}
                    className="inline-block rounded-md border border-emerald-700 px-3 py-1.5 text-emerald-200 hover:bg-emerald-900/40"
                  >
                    Open PU evidence →
                  </Link>
                </div>
              ) : null}
              <Button type="submit" disabled={busy} className="w-full sm:w-auto">
                {busy ? "Uploading…" : "Upload sheet"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </motion.div>
    </CommandShell>
  );
}
