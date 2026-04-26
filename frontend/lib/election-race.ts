import type { ElectionRace } from "./types";

/** Active races use query `race=senate`; default is presidency (param omitted). Legacy `view=senate` is still read. */
export function electionRaceFromSearchParams(sp: Pick<URLSearchParams, "get">): ElectionRace {
  if (sp.get("race") === "senate") return "senate";
  if (sp.get("view") === "senate") return "senate";
  return "presidency";
}

export function isSenateRace(sp: Pick<URLSearchParams, "get">): boolean {
  return electionRaceFromSearchParams(sp) === "senate";
}
