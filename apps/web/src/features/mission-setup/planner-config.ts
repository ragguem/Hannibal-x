export type PlannerStepId = "scenario" | "fleet" | "formation" | "execution";

export interface PlannerStep {
  id: PlannerStepId;
  title: string;
  subtitle: string;
  /** Id of the panel the step scrolls to. */
  anchor: string;
}

export const PLANNER_STEPS: readonly PlannerStep[] = [
  { id: "scenario", title: "Scénario", subtitle: "Choix du scénario", anchor: "planner-scenario" },
  { id: "fleet", title: "Flotte", subtitle: "Sélection des navires", anchor: "planner-fleet" },
  { id: "formation", title: "Formation", subtitle: "Organisation tactique", anchor: "planner-formation" },
  { id: "execution", title: "Exécution", subtitle: "Lancement de la mission", anchor: "planner-execution" },
];

export interface ExecutionOptions {
  autopilot: boolean;
  manualHelm: boolean;
}

export const DEFAULT_EXECUTION_OPTIONS: ExecutionOptions = { autopilot: false, manualHelm: false };

/** Geometry drawn by the preview only: the start contract carries no formation parameters. */
export interface FormationPlan {
  spacingKm: number;
  headingDeg: number;
}

export const DEFAULT_FORMATION_PLAN: FormationPlan = { spacingKm: 5, headingDeg: 87 };

export const SPACING_LIMITS_KM = { min: 1, max: 10, step: 0.5 } as const;

export type LevelTone = "beginner" | "confirmed" | "expert" | "free";

const LEVEL_TONES: Record<string, LevelTone> = { débutant: "beginner", confirmé: "confirmed", expert: "expert" };

export function levelTone(level: string | null | undefined): LevelTone {
  const tone = level ? LEVEL_TONES[level.toLocaleLowerCase("fr")] : undefined;
  return tone ?? "free";
}

/** Guide first, then the other ships in scenario order. */
export function fleetOrder(guide: string, ships: readonly string[]): string[] {
  return [guide, ...ships.filter((ship) => ship !== guide)];
}

export const normalizeHeading = (deg: number): number => ((Math.round(deg) % 360) + 360) % 360;
