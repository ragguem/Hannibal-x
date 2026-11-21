/** Every cache key lives here: invalidations and stream writes must hit the same keys as reads. */
export const queryKeys = {
  session: ["session"] as const,
  scenarios: ["scenarios"] as const,
  missions: ["missions"] as const,
  mission: (missionId: string) => ["missions", missionId] as const,
  recommendations: (missionId: string) => ["missions", missionId, "recommendations"] as const,
  command: (commandId: string) => ["commands", commandId] as const,
  audit: (missionId: string) => ["audit", missionId] as const,
  auditIntegrity: ["audit", "integrity"] as const,
  publications: ["doctrine", "publications"] as const,
  glossary: (query: string) => ["glossary", query] as const,
  explanation: (commandId: string) => ["commands", commandId, "explanation"] as const,
  users: ["users"] as const,
  roles: ["roles"] as const,
  shipClasses: ["catalog", "ship-classes"] as const,
  ships: ["catalog", "ships"] as const,
};
