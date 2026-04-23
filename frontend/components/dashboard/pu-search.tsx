"use client";

import { lookupPuCode } from "@/lib/api";
import { electionRaceFromSearchParams } from "@/lib/election-race";
import { electionQueryString, electionStateIdFromSearchParam } from "@/lib/url-state";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Search } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";

export function PuSearchBar({ electionId }: { electionId: number }) {
  const router = useRouter();
  const sp = useSearchParams();
  const [code, setCode] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    if (!code.trim()) return;
    setLoading(true);
    try {
      const hit = await lookupPuCode(code);
      const race = electionRaceFromSearchParams(sp);
      const stateId = electionStateIdFromSearchParam(sp.get("state_id"));
      const q = electionQueryString({
        electionId,
        race: race === "senate" ? "senate" : null,
        stateId,
      });
      router.push(`/evidence/${hit.pu_id}${q}`);
    } catch {
      setErr("No PU found for that code (try e.g. 24-11-01-001 format).");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="flex w-full max-w-xl flex-col gap-2 sm:flex-row sm:items-center">
      <div className="relative flex-1">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
        <Input
          value={code}
          onChange={(e) => setCode(e.target.value)}
          placeholder="PU code (e.g. 24-11-01-001)"
          className="pl-9"
          aria-label="Search by polling unit code"
        />
      </div>
      <Button type="submit" variant="accent" disabled={loading} className="shrink-0">
        {loading ? "…" : "Jump"}
      </Button>
      {err ? <p className="text-sm text-amber-400 sm:absolute sm:top-full sm:mt-1">{err}</p> : null}
    </form>
  );
}
