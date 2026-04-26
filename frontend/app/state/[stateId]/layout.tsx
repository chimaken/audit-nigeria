/**
 * Enables `output: 'export'`: params must be enumerated at build time.
 * IDs align with `backend/app/db/seed.py` (Lagos state + LGAs first, then FCT).
 */
export function generateStaticParams() {
  return [{ stateId: "1" }, { stateId: "2" }];
}

export default function StateSegmentLayout({ children }: { children: React.ReactNode }) {
  return children;
}
