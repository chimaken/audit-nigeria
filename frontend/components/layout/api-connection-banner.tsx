"use client";

import { getApiBase } from "@/lib/api";

function looksLikeNetworkFailure(message: string) {
  const m = message.toLowerCase();
  return (
    m.includes("failed to fetch") ||
    m.includes("networkerror") ||
    m.includes("load failed") ||
    m.includes("network request failed")
  );
}

function errorMessage(err: unknown) {
  if (err instanceof Error) return err.message;
  return String(err);
}

/** When the app cannot reach the results service. */
export function ApiConnectionBanner({ error }: { error: unknown }) {
  const apiBase = getApiBase();
  const message = errorMessage(error);
  const networkHint = looksLikeNetworkFailure(message);

  return (
    <div
      className="mb-6 rounded-xl border border-amber-800/50 bg-amber-950/25 px-4 py-4 text-left text-sm text-amber-50 shadow-sm sm:px-5"
      role="alert"
    >
      <p className="text-base font-semibold tracking-tight text-amber-100">Live results could not be loaded</p>
      <p className="mt-2 leading-relaxed text-amber-100/90">
        Try refreshing the page. If it keeps happening, check your internet connection or try again in a few minutes.
      </p>
      {networkHint ? (
        <p className="mt-2 text-sm text-amber-100/85">Your browser could not reach the results service.</p>
      ) : (
        <p className="mt-3 rounded-md bg-slate-950/40 px-3 py-2 font-mono text-xs text-slate-300">{message}</p>
      )}
      <p className="mt-3 text-xs text-amber-200/70">
        Service address:{" "}
        <span className="break-all rounded bg-slate-950/60 px-1.5 py-0.5 font-mono text-emerald-200/90">
          {apiBase}
        </span>
      </p>
    </div>
  );
}
