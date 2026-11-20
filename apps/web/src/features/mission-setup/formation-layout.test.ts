import { describe, expect, it } from "vitest";
import { columnLayout, scaleBarKm } from "./formation-layout";
import { fleetOrder, levelTone, normalizeHeading } from "./planner-config";

describe("columnLayout", () => {
  it("keeps the guide at the origin and lines the others up astern", () => {
    const placed = columnLayout(["hannibal", "alfa", "charlie"], { spacingKm: 5, headingDeg: 90 });
    expect(placed[0]).toEqual({ name: "hannibal", eastKm: -0, northKm: -0 });
    expect(placed[1]?.eastKm).toBeCloseTo(-5);
    expect(placed[1]?.northKm).toBeCloseTo(0);
    expect(placed[2]?.eastKm).toBeCloseTo(-10);
  });

  it("follows the heading", () => {
    const [, second] = columnLayout(["a", "b"], { spacingKm: 2, headingDeg: 0 });
    expect(second?.northKm).toBeCloseTo(-2);
    expect(second?.eastKm).toBeCloseTo(0);
  });
});

describe("planner helpers", () => {
  it("picks a readable scale bar", () => {
    expect(scaleBarKm(18)).toBe(10);
    expect(scaleBarKm(36)).toBe(5);
    expect(scaleBarKm(9)).toBe(20);
  });

  it("puts the guide first", () => {
    expect(fleetOrder("charlie", ["alfa", "charlie", "delta"])).toEqual(["charlie", "alfa", "delta"]);
  });

  it("wraps headings and maps levels", () => {
    expect(normalizeHeading(-1)).toBe(359);
    expect(normalizeHeading(360)).toBe(0);
    expect(levelTone("Confirmé")).toBe("confirmed");
    expect(levelTone(null)).toBe("free");
  });
});
