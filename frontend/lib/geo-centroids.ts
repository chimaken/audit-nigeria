import type { NigeriaCentroidsPayload } from "./types";

export function normalizeGeoName(s: string): string {
  return s.trim().toLowerCase().replace(/\s+/g, " ");
}

/**
 * Collapses state-name synonyms so API labels match OSGOF geo JSON
 * (e.g. `FCT` ↔ `Federal Capital Territory`).
 */
export function canonicalStateKey(name: string): string {
  const n = normalizeGeoName(name);
  if (n === "fct") return "federal capital territory";
  if (n === "federal capital territory") return "federal capital territory";
  return n;
}

export async function fetchNigeriaLgaCentroids(): Promise<NigeriaCentroidsPayload> {
  const res = await fetch("/geo/nigeria-lga-centroids.json", { cache: "force-cache" });
  if (!res.ok) {
    throw new Error(`Failed to load LGA centroids: ${res.status}`);
  }
  return res.json() as Promise<NigeriaCentroidsPayload>;
}
