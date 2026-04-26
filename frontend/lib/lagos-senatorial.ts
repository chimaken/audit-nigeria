/**
 * Demo grouping for Lagos senatorial view (presentation layer).
 * INEC senatorial boundaries are not in the API; this groups LGAs by name.
 */

import type { LgaRow, PartyResults } from "./types";

export type SenateDistrict = "Lagos West" | "Lagos East" | "Lagos Central";

const WEST = new Set([
  "Badagry",
  "Ojo",
  "Ajeromi-Ifelodun",
  "Amuwo-Odofin",
  "Surulere",
  "Oshodi-Isolo",
  "Mushin",
  "Ikeja",
]);

const EAST = new Set([
  "Ikorodu",
  "Kosofe",
  "Shomolu",
  "Epe",
  "Ibeju-Lekki",
]);

export function senateDistrictForLga(lgaName: string): SenateDistrict {
  if (WEST.has(lgaName)) return "Lagos West";
  if (EAST.has(lgaName)) return "Lagos East";
  return "Lagos Central";
}

export const SENATE_ORDER: SenateDistrict[] = [
  "Lagos West",
  "Lagos Central",
  "Lagos East",
];

export function mergePartyResults(a: PartyResults, b: PartyResults): PartyResults {
  const out: PartyResults = { ...a };
  for (const [k, v] of Object.entries(b)) {
    const key = String(k).trim().toUpperCase();
    out[key] = (out[key] ?? 0) + Number(v);
  }
  return out;
}

/** Merge verified LGA rollups into the three Lagos senatorial buckets (pilot). */
export function lagosSenateDistrictRollups(
  lgas: LgaRow[],
): Record<SenateDistrict, { parties: PartyResults; updatedAt: string | null }> {
  const empty = (): { parties: PartyResults; updatedAt: string | null } => ({
    parties: {},
    updatedAt: null,
  });
  const bucket: Record<SenateDistrict, { parties: PartyResults; updatedAt: string | null }> = {
    "Lagos West": empty(),
    "Lagos Central": empty(),
    "Lagos East": empty(),
  };
  for (const l of lgas) {
    const d = senateDistrictForLga(l.lga_name);
    const cell = bucket[d];
    cell.parties = mergePartyResults(cell.parties, l.party_results);
    if (l.updated_at) {
      if (!cell.updatedAt || l.updated_at > cell.updatedAt) {
        cell.updatedAt = l.updated_at;
      }
    }
  }
  return bucket;
}
