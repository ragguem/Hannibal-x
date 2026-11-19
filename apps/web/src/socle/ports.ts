import type { components } from "../services/openapi";

type Schemas = components["schemas"];

export type Mission = Schemas["Mission"];
export type MissionPhase = Schemas["MissionPhase"];
export type Ship = Schemas["Ship"];
export type Contact = Schemas["Contact"];
export type Classification = Schemas["Classification"];
export type RadioMessage = Schemas["RadioMessage"];
export type Objective = Schemas["Objective"];
export type Debrief = Schemas["Debrief"];
export type AuthorizationRequest = Schemas["AuthorizationRequest"];
export type ScenarioSummary = Schemas["ScenarioSummary"];
export type StartMission = Schemas["StartMission"];
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

export const PERMISSIONS = ["mission:play", "command:submit", "command:decide", "audit:read", "user:manage"] as const;
export type PermissionCode = (typeof PERMISSIONS)[number];

/** Every server call the screens may make. Implementations own URLs, credentials and error mapping. */
export interface ApiPort {
  readSession(): Promise<SessionView | null>;
  signIn(body: SignIn): Promise<SessionView>;
  signOut(): Promise<void>;
  listScenarios(): Promise<ScenarioSummary[]>;
  startMission(body: StartMission): Promise<Mission>;
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
