/**
 * Lagos: 20 LGAs (ids 1–20), FCT: 6 LGAs (ids 21–26) after seed — see `backend/app/db/seed.py`.
 */
export function generateStaticParams() {
  const lagos = Array.from({ length: 20 }, (_, i) => ({
    stateId: "1",
    lgaId: String(i + 1),
  }));
  const fct = Array.from({ length: 6 }, (_, i) => ({
    stateId: "2",
    lgaId: String(20 + i + 1),
  }));
  // Export-safe fallback routes for any runtime lga_id query value.
  const fallback = [{ stateId: "1", lgaId: "0" }, { stateId: "2", lgaId: "0" }];
  return [...lagos, ...fct, ...fallback];
}

export default function LgaSegmentLayout({ children }: { children: React.ReactNode }) {
  return children;
}
