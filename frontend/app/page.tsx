import { Suspense } from "react";
import HomeClient from "./home-client";

export default function Page() {
  return (
    <Suspense fallback={<div className="p-10 text-center text-slate-500">Loading command center…</div>}>
      <HomeClient />
    </Suspense>
  );
}
