import { Suspense } from "react";
import HomeClient from "./home-client";

function HomeLoading() {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-4 px-6 py-16 text-center">
      <div
        className="h-10 w-10 animate-spin rounded-full border-2 border-emerald-600/30 border-t-emerald-400"
        aria-hidden
      />
      <div className="max-w-md space-y-2 text-slate-300">
        <p className="text-lg font-medium text-slate-100">Loading results</p>
        <p className="text-sm leading-relaxed text-slate-400">
          This can take a moment on a slow connection. If it never loads, try refreshing the page.
        </p>
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<HomeLoading />}>
      <HomeClient />
    </Suspense>
  );
}
