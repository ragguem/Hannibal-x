/** Every cache key lives here: invalidations and stream writes must hit the same keys as reads. */
export const queryKeys = {
  session: ["session"] as const,
  scenarios: ["scenarios"] as const,
  missions: ["missions"] as const,
  mission: (missionId: string) => ["missions", missionId] as const,
  recommendations: (missionId: string) => ["missions", missionId, "recommendations"] as const,
  command: (commandId: string) => ["commands", commandId] as const,
};
