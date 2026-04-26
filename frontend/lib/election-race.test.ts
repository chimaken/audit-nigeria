import { describe, expect, it } from "vitest";

import { electionRaceFromSearchParams, isSenateRace } from "./election-race";

describe("electionRaceFromSearchParams", () => {
  it("defaults to presidency", () => {
    expect(electionRaceFromSearchParams(new URLSearchParams(""))).toBe("presidency");
  });

  it("reads race=senate", () => {
    expect(electionRaceFromSearchParams(new URLSearchParams("race=senate"))).toBe("senate");
  });

  it("reads legacy view=senate", () => {
    expect(electionRaceFromSearchParams(new URLSearchParams("view=senate"))).toBe("senate");
  });

  it("checks race=senate before falling back to view=senate", () => {
    expect(
      electionRaceFromSearchParams(new URLSearchParams("race=senate&view=foo")),
    ).toBe("senate");
  });
});

describe("isSenateRace", () => {
  it("is true only for senate", () => {
    expect(isSenateRace(new URLSearchParams("race=senate"))).toBe(true);
    expect(isSenateRace(new URLSearchParams(""))).toBe(false);
  });
});
