import { describe, expect, it } from "vitest";

import { DEFAULT_ELECTION_ID } from "./config";
import { electionQueryString, electionStateIdFromSearchParam } from "./url-state";

describe("electionStateIdFromSearchParam", () => {
  it("returns undefined for empty or invalid", () => {
    expect(electionStateIdFromSearchParam(null)).toBeUndefined();
    expect(electionStateIdFromSearchParam("")).toBeUndefined();
    expect(electionStateIdFromSearchParam("0")).toBeUndefined();
    expect(electionStateIdFromSearchParam("x")).toBeUndefined();
  });

  it("parses positive integers", () => {
    expect(electionStateIdFromSearchParam("25")).toBe(25);
    expect(electionStateIdFromSearchParam("25.7")).toBe(25);
  });
});

describe("electionQueryString", () => {
  it("includes election_id and optional state_id", () => {
    const q = electionQueryString({ electionId: 3, stateId: 12 });
    const sp = new URLSearchParams(q.startsWith("?") ? q.slice(1) : q);
    expect(sp.get("election_id")).toBe("3");
    expect(sp.get("state_id")).toBe("12");
  });

  it("uses default election when omitted", () => {
    const q = electionQueryString({});
    expect(q).toContain(`election_id=${DEFAULT_ELECTION_ID}`);
  });

  it("adds race=senate only for senate", () => {
    expect(electionQueryString({ race: "senate" })).toContain("race=senate");
    expect(electionQueryString({ race: "presidency" })).not.toContain("race=");
  });
});
