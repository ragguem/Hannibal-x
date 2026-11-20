const KNOT_MPS = 0.514444;

const pad = (n: number, width: number) => String(Math.floor(n)).padStart(width, "0");

/** 7 → "007", 360 → "000". */
export const deg3 = (deg: number): string => pad(((Math.round(deg) % 360) + 360) % 360, 3);

/** Seconds → "mm:ss" (minutes keep growing past 59). */
export const clock = (seconds: number): string => {
  const s = Math.max(0, Math.floor(seconds));
  return `${pad(s / 60, 2)}:${pad(s % 60, 2)}`;
};

/** Seconds → "15 min", rounded to the minute. */
export const minutes = (seconds: number): string => `${String(Math.round(Math.max(0, seconds) / 60))} min`;

export const knots = (mps: number): number => Math.round(mps / KNOT_MPS);

export const nm = (value: number | null | undefined, digits = 1): string =>
  value === null || value === undefined ? "—" : `${value.toFixed(digits)} NM`;
