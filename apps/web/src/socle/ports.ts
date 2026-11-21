import type { components as BackofficeComponents } from "../services/backoffice-openapi";
import type { components } from "../services/openapi";

type Schemas = components["schemas"];
type BackofficeSchemas = BackofficeComponents["schemas"];

export type UserView = BackofficeSchemas["UserViewBody"];
export type RoleView = BackofficeSchemas["RoleViewBody"];
export type CreateUser = BackofficeSchemas["CreateUserBody"];
export type IssuedPassword = BackofficeSchemas["IssuedPasswordBody"];
export type ChangePassword = BackofficeSchemas["ChangePasswordBody"];

/** The back-office also reads numbers sent as strings; the console always sends and expects numbers. */
type WithNumbers<T> = { [K in keyof T]: number extends T[K] ? number : T[K] };
export type ShipClass = WithNumbers<BackofficeSchemas["ShipClassBody"]>;
export type CatalogShip = BackofficeSchemas["ShipViewBody"];
export type CreateShip = BackofficeSchemas["CreateShipBody"];
export type ScenarioEntry = Omit<BackofficeSchemas["ScenarioEntryBody"], "published_version" | "latest_version"> & {
  published_version: number | null;
  latest_version: number;
};
export type ScenarioSummary = WithNumbers<BackofficeSchemas["ScenarioSummaryBody"]>;
/** Planned by the back-office, which freezes the published version and launches it on `apps/api`. */
export type StartMission = Omit<BackofficeSchemas["PlanMissionBody"], "participants">;
export type PlannedMission = WithNumbers<BackofficeSchemas["PlannedMissionBody"]>;
export interface MissionHistory {
  missions: PlannedMission[];
  next_cursor: string | null;
}

export type Mission = Schemas["Mission"];
export type MissionPhase = Schemas["MissionPhase"];
export type Ship = Schemas["Ship"];
export type Contact = Schemas["Contact"];
export type Classification = Schemas["Classification"];
export type RadioMessage = Schemas["RadioMessage"];
export type Objective = Schemas["Objective"];
export type Debrief = Schemas["Debrief"];
export type AuthorizationRequest = Schemas["AuthorizationRequest"];
export type SubmitOrder = Schemas["SubmitOrder"];
export type OrderMode = Schemas["OrderMode"];
export type OrderOutcome = Schemas["OrderOutcome"];
export type Command = Schemas["Command"];
export type CommandState = Schemas["CommandState"];
export type CommandDecision = Schemas["CommandDecision"];
export type Simulation = Schemas["Simulation"];
export type Recommendation = Schemas["Recommendation"];
export type SetHelm = Schemas["SetHelm"];
export type Helm = Schemas["Helm"];
export type CommandSource = Schemas["CommandSource"];
export type HeardWord = Schemas["HeardWord"];
export type VoiceOrderOutcome = Schemas["VoiceOrderOutcome"];
export type AuditEventView = Schemas["AuditEventView"];
export type AuditPage = Schemas["AuditPage"];
export type AuditIntegrity = Schemas["AuditIntegrity"];
export type AnswerLanguage = Schemas["AnswerLanguage"];
export type DoctrineQuestion = Schemas["DoctrineQuestion"];
export type DoctrineAnswer = Schemas["DoctrineAnswer"];
export type Citation = Schemas["Citation"];
export type TermSuggestion = Schemas["TermSuggestion"];
export type GlossaryEntry = Schemas["GlossaryEntry"];
export type GlossaryResult = Schemas["GlossaryResult"];
export type CommandExplanation = Schemas["CommandExplanation"];

export interface AuditQuery {
  missionId?: string;
  afterSeq?: number;
  limit?: number;
}

/** Back-office session (packages/contracts/schemas/SessionView.json — not part of the API's OpenAPI). */
export interface SessionView {
  username: string;
  role: string;
  permissions: string[];
  expires_at: string;
}

export interface SignIn {
  username: string;
  password: string;
}

export const PERMISSIONS = [
  "mission:play",
  "mission:plan",
  "command:submit",
  "command:decide",
  "audit:read",
  "user:manage",
  "catalog:manage",
  "doctrine:ask",
  "glossary:read",
  "doctrine:classified",
] as const;
export type PermissionCode = (typeof PERMISSIONS)[number];

/** Every server call the screens may make. Implementations own URLs, credentials and error mapping. */
export interface ApiPort {
  readSession(): Promise<SessionView | null>;
  signIn(body: SignIn): Promise<SessionView>;
  signOut(): Promise<void>;
  listScenarios(): Promise<ScenarioSummary[]>;
  /** Plans then launches (`mission:plan`); replaying never starts the mission twice. */
  startMission(body: StartMission): Promise<PlannedMission>;
  /** Planned missions, most recent first, with their run phase once launched. */
  listMissionHistory(cursor?: string): Promise<MissionHistory>;
  archiveMission(missionId: string): Promise<PlannedMission>;
  readMission(missionId: string): Promise<Mission>;
  stopMission(missionId: string): Promise<void>;
  submitOrder(missionId: string, body: SubmitOrder): Promise<OrderOutcome>;
  simulateOrder(missionId: string, text: string): Promise<Simulation>;
  readCommand(commandId: string): Promise<Command>;
  decideCommand(commandId: string, decision: CommandDecision): Promise<Command>;
  listRecommendations(missionId: string): Promise<Recommendation[]>;
  setHelm(missionId: string, body: SetHelm): Promise<Helm>;
  classifyContact(missionId: string, contactId: string, classification: Classification): Promise<void>;
  replyRequest(missionId: string, ship: string, approve: boolean): Promise<void>;
  setAutopilot(missionId: string, enabled: boolean): Promise<void>;
  /** `parentId`: the command this recording corrects. */
  submitVoiceOrder(missionId: string, recording: Blob, parentId?: string): Promise<VoiceOrderOutcome>;
  readAudit(query: AuditQuery): Promise<AuditPage>;
  verifyAudit(): Promise<AuditIntegrity>;
  /** Address of a voice command's recording, for an `<audio>` element (same session cookie). */
  recordingUrl(commandId: string): string;
  /** Cited answer or refusal; classified publications are searched only if the session allows it. */
  askDoctrine(body: DoctrineQuestion): Promise<DoctrineAnswer>;
  /** Publications the session may restrict a question to. */
  listPublications(): Promise<string[]>;
  searchGlossary(query: string): Promise<GlossaryResult>;
  explainCommand(commandId: string): Promise<CommandExplanation>;
  /** Accounts (back-office, `user:manage`). */
  listUsers(): Promise<UserView[]>;
  listRoles(): Promise<RoleView[]>;
  /** The temporary password is shown once and never readable again. */
  createUser(body: CreateUser): Promise<IssuedPassword>;
  changeUserRole(userId: string, role: string): Promise<UserView>;
  disableUser(userId: string): Promise<UserView>;
  enableUser(userId: string): Promise<UserView>;
  resetUserPassword(userId: string): Promise<IssuedPassword>;
  /** Every session of the user is revoked: they sign in again with the new password. */
  changeOwnPassword(body: ChangePassword): Promise<void>;
  /** Ship catalog (back-office, `catalog:manage`). Nothing is deleted: a ship is retired. */
  listShipClasses(): Promise<ShipClass[]>;
  createShipClass(body: ShipClass): Promise<ShipClass>;
  listShips(): Promise<CatalogShip[]>;
  createShip(body: CreateShip): Promise<CatalogShip>;
  changeShipClass(shipId: string, classCode: string): Promise<CatalogShip>;
  retireShip(shipId: string): Promise<CatalogShip>;
  reactivateShip(shipId: string): Promise<CatalogShip>;
  /** Scenario catalog (back-office, `catalog:manage`): immutable versions, one published, archived rather than deleted. */
  listCatalogScenarios(): Promise<ScenarioEntry[]>;
  importScenario(yaml: string): Promise<ScenarioEntry>;
  publishScenario(id: string, version: number): Promise<ScenarioEntry>;
  archiveScenario(id: string): Promise<ScenarioEntry>;
  exportScenario(id: string, version: number): Promise<string>;
}

export type StreamEvent = { type: "situation"; mission: Mission } | { type: "phase"; phase: MissionPhase };

/** `polling`: the live stream dropped and the mission is re-read every 2 s until it comes back. */
export type StreamStatus = "connecting" | "live" | "polling" | "closed";

export interface StreamHandlers {
  onEvent: (event: StreamEvent) => void;
  onStatus: (status: StreamStatus) => void;
}

export interface StreamPort {
  /** Returns the unsubscribe function. */
  subscribe(missionId: string, handlers: StreamHandlers): () => void;
}
