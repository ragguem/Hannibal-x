import type { FormationPlan } from "./planner-config";

export interface PlacedShip {
  name: string;
  eastKm: number;
  northKm: number;
}

const DEG_TO_RAD = Math.PI / 180;

/** Column: each ship keeps `spacingKm` astern of the one ahead, on the reciprocal of the heading. */
export function columnLayout(order: readonly string[], plan: FormationPlan): PlacedShip[] {
  const heading = plan.headingDeg * DEG_TO_RAD;
  return order.map((name, rank) => ({
    name,
    eastKm: -Math.sin(heading) * plan.spacingKm * rank,
    northKm: -Math.cos(heading) * plan.spacingKm * rank,
  }));
}

/** Shortest "nice" distance (1, 2, 5 × 10ⁿ km) drawn at least `minPx` long. */
export function scaleBarKm(pxPerKm: number, minPx = 120): number {
  for (let magnitude = 0.1; magnitude < 1e4; magnitude *= 10) {
    for (const factor of [1, 2, 5]) {
      const km = factor * magnitude;
      if (km * pxPerKm >= minPx) return Number(km.toPrecision(1));
    }
  }
  return 1e4;
}
