import { describe, expect, it } from "vitest";
import { inside, project } from "../features/radar/radar-geometry";
import { clock, deg3, knots, nm } from "./format";

describe("format", () => {
  it("formats headings, clocks, speeds and distances", () => {
    expect(deg3(7)).toBe("007");
    expect(deg3(360)).toBe("000");
    expect(deg3(-10)).toBe("350");
    expect(clock(65)).toBe("01:05");
    expect(clock(-3)).toBe("00:00");
    expect(knots(12 * 0.514444)).toBe(12);
    expect(nm(null)).toBe("—");
    expect(nm(1.234)).toBe("1.2 NM");
  });
});

describe("radar geometry", () => {
  it("projects north up around the origin", () => {
    const p = project(1852, 1852, { east: 0, north: 0 }, 2, 200);
    expect(p).toEqual({ x: 100, y: -100 });
    expect(inside(p, 200)).toBe(true);
    expect(inside(project(0, 1852 * 3, { east: 0, north: 0 }, 2, 200), 200)).toBe(false);
  });
});
