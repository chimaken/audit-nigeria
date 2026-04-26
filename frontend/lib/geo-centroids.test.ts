import { describe, expect, it } from "vitest";

import { canonicalStateKey, normalizeGeoName } from "./geo-centroids";

describe("normalizeGeoName", () => {
  it("trims and collapses whitespace", () => {
    expect(normalizeGeoName("  Lagos   Island  ")).toBe("lagos island");
  });
});

describe("canonicalStateKey", () => {
  it("maps FCT synonyms to federal capital territory", () => {
    expect(canonicalStateKey("FCT")).toBe("federal capital territory");
    expect(canonicalStateKey("Federal Capital Territory")).toBe("federal capital territory");
  });

  it("passes through other states lowercased", () => {
    expect(canonicalStateKey("Lagos")).toBe("lagos");
  });
});
