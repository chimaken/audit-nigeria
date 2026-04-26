import { DEFAULT_ELECTION_ID } from "./config";
import type { ElectionRace } from "./types";

/** Valid `state_id` query value, or `undefined` if absent or invalid. */
export function electionStateIdFromSearchParam(value: string | null): number | undefined {
  if (value == null || value === "") return undefined;
  const n = Number(value);
  return Number.isFinite(n) && n >= 1 ? Math.floor(n) : undefined;
}

/** Build `?election_id=&race=senate&state_id=` for shareable drill-down links. Presidency omits `race`. */
export function electionQueryString(params: {
  electionId?: number;
  /** When `"senate"`, adds `race=senate`. Presidency is the default and is not written to the URL. */
  race?: ElectionRace | null;
  stateId?: number | null;
}): string {
  const sp = new URLSearchParams();
  sp.set("election_id", String(params.electionId ?? DEFAULT_ELECTION_ID));
  if (params.race === "senate") {
    sp.set("race", "senate");
  }
  const sid = params.stateId;
  if (sid != null && Number.isFinite(sid) && sid >= 1) {
    sp.set("state_id", String(Math.floor(Number(sid))));
  }
  return `?${sp.toString()}`;
}
