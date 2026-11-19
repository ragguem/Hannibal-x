export const NM_M = 1852;
export const RANGES_NM = [1, 2, 4, 8, 16] as const;
export type RangeNm = (typeof RANGES_NM)[number];

export interface Point {
  x: number;
  y: number;
}

/** Local east/north metres → SVG coordinates, north up, centred on `origin`. */
export function project(east: number, north: number, origin: { east: number; north: number }, rangeNm: number, radius: number): Point {
  const scale = radius / (rangeNm * NM_M);
  return { x: (east - origin.east) * scale, y: -(north - origin.north) * scale };
}

export const inside = (p: Point, radius: number): boolean => Math.hypot(p.x, p.y) <= radius;
