"use client";

import Link from "next/link";
import { Suspense } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { ChevronRight, Radio } from "lucide-react";
import { cn } from "@/lib/utils";
import { PuSearchBar } from "@/components/dashboard/pu-search";
import { ElectionToggle } from "@/components/dashboard/election-toggle";
import { electionQueryString, electionStateIdFromSearchParam } from "@/lib/url-state";
import { electionRaceFromSearchParams } from "@/lib/election-race";

function ShellUploadLink({ electionId }: { electionId: number }) {
  const sp = useSearchParams();
  const race = electionRaceFromSearchParams(sp);
  const stateId = electionStateIdFromSearchParam(sp.get("state_id"));
  const q = electionQueryString({
    electionId,
    race: race === "senate" ? "senate" : null,
    stateId,
  });
  return (
    <Link
      href={`/upload${q}`}
      className="rounded-md px-2 py-1 text-sm font-medium text-slate-400 transition-colors hover:bg-slate-800/80 hover:text-emerald-400"
    >
      Upload
    </Link>
  );
}

export function CommandShell({
  children,
  electionId,
  crumbs,
}: {
  children: React.ReactNode;
  electionId: number;
  crumbs: { href?: string; label: string }[];
}) {
  const pathname = usePathname();

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 border-b border-command-border bg-command-bg/95 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center gap-1">
              <Link href="/" className="flex items-center gap-2 text-lg font-bold tracking-tight text-slate-50">
                <span className="flex h-8 w-8 items-center justify-center rounded-md bg-emerald-600/20 text-emerald-400">
                  <Radio className="h-4 w-4" />
                </span>
                AuditNigeria
                <span className="rounded bg-slate-800 px-2 py-0.5 text-xs font-normal text-slate-400">
                  Command
                </span>
              </Link>
              <Suspense fallback={<span className="h-8 w-16 animate-pulse rounded-md bg-slate-800/60" />}>
                <ShellUploadLink electionId={electionId} />
              </Suspense>
            </div>
            <nav className="flex flex-wrap items-center gap-1 text-sm text-slate-400">
              {crumbs.map((c, i) => (
                <span key={`${c.label}-${i}`} className="flex items-center gap-1">
                  {i > 0 ? <ChevronRight className="h-3 w-3 shrink-0 text-slate-600" /> : null}
                  {c.href ? (
                    <Link
                      href={c.href}
                      className={cn(
                        "rounded px-1 hover:text-emerald-400",
                        pathname === c.href.split("?")[0] && "text-emerald-400",
                      )}
                    >
                      {c.label}
                    </Link>
                  ) : (
                    <span className="text-slate-200">{c.label}</span>
                  )}
                </span>
              ))}
            </nav>
          </div>
          <div className="flex flex-col gap-3 lg:items-end">
            <Suspense
              fallback={<div className="h-9 w-56 animate-pulse rounded-lg bg-slate-800/80" />}
            >
              <ElectionToggle />
            </Suspense>
            <Suspense fallback={<div className="h-10 max-w-xl animate-pulse rounded-lg bg-slate-800/80" />}>
              <PuSearchBar electionId={electionId} />
            </Suspense>
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6">{children}</main>
    </div>
  );
}
