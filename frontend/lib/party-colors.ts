/** Crisis command-center palette: leading party → map / badge color */

const FALLBACK = "#64748b";

const MAP: Record<string, string> = {
  APC: "#16a34a",
  PDP: "#dc2626",
  LP: "#7c3aed",
  NNPP: "#0891b2",
  ADC: "#ca8a04",
  APGA: "#65a30d",
  SDP: "#ea580c",
  A: "#94a3b8",
  AA: "#94a3b8",
};

export function partyColor(acronym: string): string {
  const k = acronym.trim().toUpperCase();
  return MAP[k] ?? FALLBACK;
}

export function leadingParty(parties: Record<string, number>): string | null {
  const entries = Object.entries(parties).filter(([, v]) => v > 0);
  if (!entries.length) return null;
  entries.sort((a, b) => b[1] - a[1]);
  return entries[0][0];
}
