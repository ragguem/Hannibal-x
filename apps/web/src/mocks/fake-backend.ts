import type {
  AuditEventView,
  AuditIntegrity,
  AuditPage,
  AuditQuery,
  AuthorizationRequest,
  Citation,
  Classification,
  Command,
  CommandDecision,
  CommandExplanation,
  DoctrineAnswer,
  DoctrineQuestion,
  GlossaryEntry,
  GlossaryResult,
  CommandSource,
  ChangePassword,
  CreateShip,
  CreateUser,
  IssuedPassword,
  RoleView,
  CatalogShip,
  ScenarioEntry,
  ShipClass,
  UserView,
  VoiceOrderOutcome,
  Mission,
  MissionHistory,
  Objective,
  PlannedMission,
  OrderOutcome,
  RadioMessage,
  Recommendation,
  ScenarioSummary,
  SessionView,
  SetHelm,
  Simulation,
  StartMission,
  SubmitOrder,
} from "../socle/ports";

/** Invented data for the mocked console: nothing here comes from a publication. */
const SCENARIOS: ScenarioSummary[] = [
  {
    id: "transit-colonne",
    title: "Transit en colonne",
    level: "débutant",
    summary: "Tenir son poste dans une colonne de quatre navires.",
    briefing: "La force transite en colonne derrière HANNIBAL. Une piste de surface approche par tribord.",
    duration_s: 900,
    guide_ship: "hannibal",
    playable_ships: ["hannibal", "alfa", "charlie", "delta"],
  },
  {
    id: "ecran-anti-surface",
    title: "Écran anti-surface",
    level: "confirmé",
    summary: "Écran en ligne de front face à une menace de surface.",
    briefing: null,
    duration_s: 1200,
    guide_ship: "hannibal",
    playable_ships: ["hannibal", "alfa", "charlie"],
  },
];

const FAKE_ROLES: RoleView[] = [
  {
    code: "instructeur",
    label: "Instructeur",
    permissions: [
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
    ],
  },
  { code: "eleve", label: "Élève", permissions: ["mission:play", "command:submit", "doctrine:ask", "glossary:read"] },
];

/** Invented accounts; both sign in with the password `demo`. */
const SEED_ACCOUNTS: FakeAccount[] = [
  { id: "0190a000-0000-7000-8000-000000000001", username: "eleve", role: "eleve" },
  { id: "0190a000-0000-7000-8000-000000000002", username: "instructeur", role: "instructeur" },
].map((a) => ({ ...a, password: "demo", created_at: "2026-01-05T08:00:00Z", disabled_at: null, password_changed_at: "2026-01-05T08:00:00Z" }));

export interface FakeAccount extends UserView {
  password: string;
}

/** Invented catalog, the call signs of the repository scenarios. */
const SEED_SHIP_CLASSES: ShipClass[] = [
  { code: "aviso", label: "Aviso", min_speed_knots: 3, max_speed_knots: 24, turn_radius_meters: 400, length_meters: 81 },
  { code: "fregate", label: "Frégate", min_speed_knots: 3, max_speed_knots: 28, turn_radius_meters: 600, length_meters: 142 },
];
const SEED_SHIPS: CatalogShip[] = (
  [
    ["alfa", "fregate"],
    ["charlie", "aviso"],
    ["delta", "aviso"],
    ["hannibal", "fregate"],
  ] as const
).map(([call_sign, class_code], i) => ({
  id: `0190b000-0000-7000-8000-00000000000${i + 1}`,
  call_sign,
  class_code,
  active: true,
  created_at: "2026-01-05T08:00:00Z",
  retired_at: null,
}));
const CLASS_CODE = /^[a-z][a-z0-9_-]{1,31}$/;
const CALL_SIGN = /^[a-z][a-z0-9-]{1,23}$/;

const USERNAME = /^[a-z0-9._-]{3,32}$/;
const MIN_PASSWORD_LENGTH = 12;

/** Invented passages: the mocked doctrine answers about speed and replenishment, and refuses the rest. */
const SAMPLE_PASSAGES: { citation: Citation; keywords: string[]; answer: string }[] = [
  {
    citation: {
      number: 1,
      passage_id: 2,
      publication: "DEMO-MANUEL",
      article: "102",
      title: "Formation speed",
      page: "1-4",
      text: "The formation speed is ordered by the guide. The standard tactical speed is 12 knots unless another speed is ordered.",
    },
    keywords: ["vitesse", "speed"],
    answer: "La vitesse tactique standard est de 12 nœuds, sauf autre vitesse ordonnée [1].",
  },
  {
    citation: {
      number: 1,
      passage_id: 3,
      publication: "DEMO-MANUEL",
      article: "205",
      title: "Replenishment at sea approach",
      page: "2-7",
      text: "During a replenishment at sea approach, the receiving ship keeps a separation of 40 metres from the delivering ship.",
    },
    keywords: ["ravitaillement", "replenishment", "ras"],
    answer: "Le bâtiment ravitaillé garde un écart de 40 mètres avec le ravitailleur [1].",
  },
  {
    citation: {
      number: 1,
      passage_id: 9,
      publication: "DEMO-RESTREINT",
      article: "C-1",
      title: "Silent manoeuvres",
      text: "The silent manoeuvre procedure is described in the restricted annex.",
    },
    keywords: ["silencieu", "silent"],
    answer: "La procédure de manœuvre silencieuse figure dans l'annexe restreinte [1].",
  },
];

const SAMPLE_GLOSSARY: GlossaryEntry[] = [
  { en: "replenishment at sea", fr: "ravitaillement à la mer", abbreviation: "RAS", source: "DEMO-GLOSSAIRE", definition_fr: "Transfert de combustible ou de vivres entre navires en route." },
  { en: "officer in tactical command", fr: "commandant tactique", abbreviation: "OTC", source: "DEMO-GLOSSAIRE" },
  { en: "station", fr: "poste", source: "DEMO-GLOSSAIRE", definition_fr: "Position assignée dans la formation." },
];

const KN = 0.514444;
const NM = 1852;
const D2R = Math.PI / 180;
const SPACING_M = 400;

interface Leg {
  at_s: number;
  east_m: number;
  north_m: number;
  course_deg: number;
  speed_kn: number;
}

interface MissionRecord {
  id: string;
  scenario: ScenarioSummary;
  player: string;
  startedAt: number;
  stoppedAt_s: number | null;
  autopilot: boolean;
  manualHelm: boolean;
  leg: Leg;
  helm: { course_deg: number; speed_kn: number; rudder: number };
  classification: Classification;
  requests: AuthorizationRequest[];
  radio: RadioMessage[];
  pending: string[];
  acknowledgedAt_s: number | null;
  classifiedAt_s: number | null;
}

interface CommandRecord extends Command {
  dispatchAt: number | null;
}

export interface FakeState {
  session: SessionView | null;
  missions: MissionRecord[];
  commands: CommandRecord[];
  audit: AuditEventView[];
  seq: number;
  /** Absent from states saved before accounts existed: seeded on first use. */
  accounts?: FakeAccount[];
  catalog?: { classes: ShipClass[]; ships: CatalogShip[] };
  scenarioCatalog?: (ScenarioEntry & { sources: string[] })[];
  planned?: PlannedMission[];
}

/** What the fake "hears" in every recording, unless a test sets `FakeBackend.heard`. */
export const FAKE_HEARD_ORDER = "ALL SHIPS CORPEN 045 SPEED 12";
const MIN_RECORDING_BYTES = 2000;

export class FakeError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

const invalid = () => new FakeError(422, "invalid_request", "Requête refusée.");

const toUserView = ({ id, username, role, created_at, disabled_at, password_changed_at }: FakeAccount): UserView => ({
  id,
  username,
  role,
  created_at,
  disabled_at,
  password_changed_at,
});

const temporaryPassword = () => {
  const bytes = crypto.getRandomValues(new Uint8Array(12));
  return Array.from(bytes, (b) => b.toString(36).padStart(2, "0")).join("");
};

const wrap = (deg: number) => ((deg % 360) + 360) % 360;
const advance = (leg: Leg, t: number) => {
  const d = (t - leg.at_s) * leg.speed_kn * KN;
  return { east: leg.east_m + Math.sin(leg.course_deg * D2R) * d, north: leg.north_m + Math.cos(leg.course_deg * D2R) * d };
};

/** Parses the few signals the fake understands; anything else is refused like the real grammar would. */
function parseOrder(text: string): { course?: number; speed?: number; fr: string } | null {
  const corpen = /\bCORPEN (\d{3})\b/.exec(text);
  const turn = /\bTURN (\d{1,3}) (STBD|PORT)\b/.exec(text);
  const speed = /\bSPEED (\d{1,2})\b/.exec(text);
  if (!corpen && !turn && !speed) return null;
  const parts: string[] = [];
  const out: { course?: number; speed?: number; fr: string } = { fr: "" };
  if (corpen) {
    out.course = Number(corpen[1]);
    parts.push(`faire route au ${corpen[1]}°`);
  }
  if (turn) {
    out.course = Number(turn[1]) * (turn[2] === "STBD" ? 1 : -1);
    parts.push(`venir de ${turn[1]}° sur ${turn[2] === "STBD" ? "tribord" : "bâbord"}`);
  }
  if (speed) {
    out.speed = Number(speed[1]);
    parts.push(`vitesse ${speed[1]} nœuds`);
  }
  out.fr = parts.join(", ");
  return out;
}

export class FakeBackend {
  state: FakeState = { session: null, missions: [], commands: [], audit: [], seq: 0 };
  heard = FAKE_HEARD_ORDER;
  /** Recordings stay in memory: they are not shared with the 3D frame and vanish on reload. */
  readonly recordings = new Map<string, Blob>();

  constructor(private readonly now: () => number = () => Date.now()) {}

  // ------------------------------------------------------------------ session
  readSession(): SessionView | null {
    return this.state.session;
  }

  signIn(username: string, password: string): SessionView {
    const account = this.accounts().find((a) => a.username === username && a.disabled_at === null);
    if (account?.password !== password) throw new FakeError(401, "invalid_credentials", "Identifiants invalides.");
    const expires = new Date(this.now() + 8 * 3600_000).toISOString();
    this.state.session = { username, role: account.role, permissions: this.permissionsOf(account.role), expires_at: expires };
    return this.state.session;
  }

  // ------------------------------------------------------------------ accounts
  listUsers(): UserView[] {
    this.require("user:manage");
    return this.accounts()
      .map(toUserView)
      .sort((a, b) => a.username.localeCompare(b.username));
  }

  listRoles(): RoleView[] {
    this.require("user:manage");
    return FAKE_ROLES;
  }

  createUser({ username, role }: CreateUser): IssuedPassword {
    this.require("user:manage");
    if (!USERNAME.test(username)) throw invalid();
    this.requireRole(role);
    if (this.accounts().some((a) => a.username === username)) {
      throw new FakeError(409, "conflict", "Conflit avec l'état actuel.");
    }
    const password = temporaryPassword();
    const account: FakeAccount = {
      id: crypto.randomUUID(),
      username,
      role,
      password,
      created_at: new Date(this.now()).toISOString(),
      disabled_at: null,
      password_changed_at: null,
    };
    this.accounts().push(account);
    return { user: toUserView(account), temporary_password: password };
  }

  changeUserRole(userId: string, role: string): UserView {
    this.require("user:manage");
    const account = this.otherAccount(userId);
    this.requireRole(role);
    account.role = role;
    return toUserView(account);
  }

  disableUser(userId: string): UserView {
    this.require("user:manage");
    const account = this.otherAccount(userId);
    account.disabled_at = new Date(this.now()).toISOString();
    return toUserView(account);
  }

  enableUser(userId: string): UserView {
    this.require("user:manage");
    const account = this.account(userId);
    account.disabled_at = null;
    return toUserView(account);
  }

  resetUserPassword(userId: string): IssuedPassword {
    this.require("user:manage");
    const account = this.account(userId);
    account.password = temporaryPassword();
    account.password_changed_at = null;
    return { user: toUserView(account), temporary_password: account.password };
  }

  changeOwnPassword({ current_password, new_password }: ChangePassword) {
    const s = this.state.session;
    if (!s) throw new FakeError(401, "unauthenticated", "Session absente ou expirée.");
    const account = this.accounts().find((a) => a.username === s.username);
    if (account?.password !== current_password) throw invalid();
    if (new_password.length < MIN_PASSWORD_LENGTH || new_password === current_password) throw invalid();
    account.password = new_password;
    account.password_changed_at = new Date(this.now()).toISOString();
    this.state.session = null;
  }

  // ------------------------------------------------------------------ ship catalog
  listShipClasses(): ShipClass[] {
    this.require("catalog:manage");
    return [...this.catalog().classes].sort((a, b) => a.code.localeCompare(b.code));
  }

  createShipClass(body: ShipClass): ShipClass {
    this.require("catalog:manage");
    const shipClass = { ...body, label: body.label.trim() };
    const { min_speed_knots: min, max_speed_knots: max, turn_radius_meters: radius, length_meters: length } = shipClass;
    const valid = CLASS_CODE.test(shipClass.code) && shipClass.label.length > 0 && min > 0 && min <= max && max <= 60;
    if (!valid || !(radius > 0 && radius <= 5000) || !(length > 0 && length <= 500)) throw invalid();
    if (this.catalog().classes.some((c) => c.code === shipClass.code)) throw new FakeError(409, "conflict", "Conflit avec l'état actuel.");
    this.catalog().classes.push(shipClass);
    return shipClass;
  }

  listShips(): CatalogShip[] {
    this.require("catalog:manage");
    return [...this.catalog().ships].sort((a, b) => a.call_sign.localeCompare(b.call_sign));
  }

  createShip({ call_sign, class_code }: CreateShip): CatalogShip {
    this.require("catalog:manage");
    if (!CALL_SIGN.test(call_sign)) throw invalid();
    this.requireShipClass(class_code);
    if (this.catalog().ships.some((s) => s.call_sign === call_sign)) throw new FakeError(409, "conflict", "Conflit avec l'état actuel.");
    const ship: CatalogShip = {
      id: crypto.randomUUID(),
      call_sign,
      class_code,
      active: true,
      created_at: new Date(this.now()).toISOString(),
      retired_at: null,
    };
    this.catalog().ships.push(ship);
    return ship;
  }

  changeShipClass(shipId: string, classCode: string): CatalogShip {
    this.require("catalog:manage");
    this.requireShipClass(classCode);
    return Object.assign(this.ship(shipId), { class_code: classCode });
  }

  retireShip(shipId: string): CatalogShip {
    this.require("catalog:manage");
    return Object.assign(this.ship(shipId), { active: false, retired_at: new Date(this.now()).toISOString() });
  }

  reactivateShip(shipId: string): CatalogShip {
    this.require("catalog:manage");
    return Object.assign(this.ship(shipId), { active: true, retired_at: null });
  }

  // ------------------------------------------------------------------ scenario catalog
  listCatalogScenarios(): ScenarioEntry[] {
    this.require("catalog:manage");
    return this.scenarioCatalog()
      .map((e) => this.scenarioEntry(e.id))
      .sort((a, b) => a.id.localeCompare(b.id));
  }

  /** Reads only `id`, `titre` and `niveau`: the real schema check is the back-office's. */
  importScenario(yaml: string): ScenarioEntry {
    this.require("catalog:manage");
    const field = (name: string) => new RegExp(`^${name}:\\s*(.+)$`, "m").exec(yaml)?.[1]?.trim();
    const id = field("id");
    if (!id) throw new FakeError(422, "invalid_request", "Scénario non conforme en / : id manquant");
    let entry = this.scenarioCatalog().find((e) => e.id === id);
    if (entry?.archived_at) throw new FakeError(409, "conflict", `Le scénario « ${id} » est archivé.`);
    if (!entry) {
      entry = { id, title: field("titre") ?? id, level: field("niveau") ?? "", published_version: null, latest_version: 0, archived_at: null, sources: [] };
      this.scenarioCatalog().push(entry);
    }
    if (entry.sources.at(-1) !== yaml) {
      entry.sources.push(yaml);
      entry.latest_version = entry.sources.length;
    }
    return this.scenarioEntry(id);
  }

  publishScenario(id: string, version: number): ScenarioEntry {
    this.require("catalog:manage");
    const entry = this.catalogScenario(id);
    if (entry.archived_at) throw new FakeError(409, "conflict", "Conflit avec l'état actuel.");
    if (version < 1 || version > entry.latest_version) throw invalid();
    entry.published_version = version;
    return this.scenarioEntry(id);
  }

  archiveScenario(id: string): ScenarioEntry {
    this.require("catalog:manage");
    this.catalogScenario(id).archived_at ??= new Date(this.now()).toISOString();
    return this.scenarioEntry(id);
  }

  exportScenario(id: string, version: number): string {
    this.require("catalog:manage");
    const source = this.catalogScenario(id).sources[version - 1];
    if (source === undefined) throw new FakeError(404, "not_found", "Ressource introuvable.");
    return source;
  }

  private scenarioCatalog() {
    this.state.scenarioCatalog ??= SCENARIOS.map((s) => ({
      id: s.id,
      title: s.title,
      level: s.level ?? "",
      published_version: 1,
      latest_version: 1,
      archived_at: null,
      sources: [`schema_version: 1\nid: ${s.id}\ntitre: ${s.title}\nniveau: ${s.level ?? ""}\n`],
    }));
    return this.state.scenarioCatalog;
  }

  private catalogScenario(id: string) {
    const entry = this.scenarioCatalog().find((e) => e.id === id);
    if (!entry) throw new FakeError(404, "not_found", "Ressource introuvable.");
    return entry;
  }

  private scenarioEntry(id: string): ScenarioEntry {
    const e = this.catalogScenario(id);
    return { id: e.id, title: e.title, level: e.level, published_version: e.published_version, latest_version: e.latest_version, archived_at: e.archived_at };
  }

  private catalog(): { classes: ShipClass[]; ships: CatalogShip[] } {
    this.state.catalog ??= { classes: SEED_SHIP_CLASSES.map((c) => ({ ...c })), ships: SEED_SHIPS.map((s) => ({ ...s })) };
    return this.state.catalog;
  }

  private requireShipClass(code: string) {
    if (!this.catalog().classes.some((c) => c.code === code)) throw invalid();
  }

  private ship(shipId: string): CatalogShip {
    const ship = this.catalog().ships.find((s) => s.id === shipId);
    if (!ship) throw new FakeError(404, "not_found", "Ressource introuvable.");
    return ship;
  }

  private accounts(): FakeAccount[] {
    this.state.accounts ??= SEED_ACCOUNTS.map((a) => ({ ...a }));
    return this.state.accounts;
  }

  private permissionsOf(role: string): string[] {
    return FAKE_ROLES.find((r) => r.code === role)?.permissions ?? [];
  }

  private requireRole(role: string) {
    if (!FAKE_ROLES.some((r) => r.code === role)) throw invalid();
  }

  private account(userId: string): FakeAccount {
    const account = this.accounts().find((a) => a.id === userId);
    if (!account) throw new FakeError(404, "not_found", "Ressource introuvable.");
    return account;
  }

  /** An administrator neither disables nor demotes themself. */
  private otherAccount(userId: string): FakeAccount {
    const account = this.account(userId);
    if (account.username === this.state.session?.username) throw invalid();
    return account;
  }

  signOut() {
    this.state.session = null;
  }

  private require(permission: string) {
    const s = this.state.session;
    if (!s) throw new FakeError(401, "unauthenticated", "Session absente ou expirée.");
    if (!s.permissions.includes(permission)) throw new FakeError(403, "forbidden", "Action non autorisée.");
  }

  // ------------------------------------------------------------------ missions
  listScenarios(): ScenarioSummary[] {
    this.require("mission:play");
    return SCENARIOS;
  }

  /** What the back-office does: plan, then launch on the simulator under the same id. */
  planAndLaunch(body: StartMission): PlannedMission {
    this.require("mission:plan");
    const mission = this.startMission(body);
    const planned: PlannedMission = {
      id: mission.id,
      scenario_id: body.scenario_id,
      scenario_version: 1,
      scenario_title: SCENARIOS.find((s) => s.id === body.scenario_id)?.title ?? body.scenario_id,
      player_ship: body.player_ship,
      autopilot: body.autopilot,
      manual_helm: body.manual_helm,
      state: "running",
      created_at: new Date(this.now()).toISOString(),
      launched_at: new Date(this.now()).toISOString(),
      archived_at: null,
      run_phase: "running",
      finished_at: null,
      participants: [],
    };
    (this.state.planned ??= []).unshift(planned);
    return planned;
  }

  listMissionHistory(): MissionHistory {
    this.require("mission:plan");
    return { missions: this.state.planned ?? [], next_cursor: null };
  }

  /** Already launched by `planAndLaunch`: replaying returns it unchanged. */
  launchMission(id: string): PlannedMission {
    this.require("mission:plan");
    const planned = this.state.planned?.find((m) => m.id === id);
    if (!planned) throw new FakeError(404, "not_found", "Mission inconnue.");
    return planned;
  }

  archiveMission(id: string): PlannedMission {
    const planned = this.launchMission(id);
    planned.state = "archived";
    planned.archived_at = new Date(this.now()).toISOString();
    return planned;
  }

  /** The simulator side: tests start a mission directly, as `apps/api` does on launch. */
  startMission(body: StartMission): Mission {
    this.require("mission:play");
    const scenario = SCENARIOS.find((s) => s.id === body.scenario_id);
    if (!scenario) throw new FakeError(404, "scenario_not_found", "Scénario inconnu.");
    if (!scenario.playable_ships.includes(body.player_ship)) {
      throw new FakeError(422, "ship_not_playable", "Ce navire ne peut pas être tenu.");
    }
    const id = `m-${String(++this.state.seq)}`;
    const record: MissionRecord = {
      id,
      scenario,
      player: body.player_ship,
      startedAt: this.now(),
      stoppedAt_s: null,
      autopilot: body.autopilot,
      manualHelm: body.manual_helm,
      leg: { at_s: 0, east_m: 0, north_m: 0, course_deg: 20, speed_kn: 12 },
      helm: { course_deg: 20, speed_kn: 12, rudder: 0 },
      classification: "inconnu",
      requests: [
        { ship: "charlie", requested_at_s: 0, contact_id: "TRK021", text_fr: "CHARLIE demande à reconnaître TRK021." },
      ],
      radio: [
        {
          id: 1,
          kind: "ordre",
          sender: scenario.guide_ship.toUpperCase(),
          recipient: "TOUS",
          sent_at_s: 0,
          text_en: "ALL SHIPS THIS IS HANNIBAL CORPEN 020 SPEED 12 OVER",
          text_fr: "À tous : faire route au 020°, vitesse 12 nœuds",
        },
      ],
      pending: ["CORPEN 020 SPEED 12"],
      acknowledgedAt_s: null,
      classifiedAt_s: null,
    };
    this.state.missions.push(record);
    this.log("mission_started", { scenario_id: scenario.id, player_ship: body.player_ship }, { missionId: id });
    return this.snapshot(record);
  }

  readMission(id: string): Mission {
    this.require("mission:play");
    return this.snapshot(this.mission(id));
  }

  stopMission(id: string) {
    this.require("mission:play");
    const m = this.mission(id);
    m.stoppedAt_s ??= this.elapsed(m);
  }

  setAutopilot(id: string, enabled: boolean) {
    this.require("mission:play");
    this.running(id).autopilot = enabled;
  }

  classifyContact(id: string, contactId: string, classification: Classification) {
    this.require("mission:play");
    const m = this.running(id);
    if (contactId !== "TRK021") throw new FakeError(404, "contact_not_found", "Piste inconnue.");
    m.classification = classification;
    m.classifiedAt_s = this.elapsed(m);
  }

  replyRequest(id: string, ship: string, approve: boolean) {
    this.require("command:decide");
    const m = this.running(id);
    m.requests = m.requests.filter((r) => r.ship !== ship);
    this.radio(m, "joueur", m.scenario.guide_ship.toUpperCase(), ship.toUpperCase(), approve ? "APPROVED" : "DENIED", approve ? "Accordé" : "Refusé");
  }

  setHelm(id: string, body: SetHelm) {
    this.require("mission:play");
    const m = this.running(id);
    if (!m.manualHelm) throw new FakeError(409, "helm_not_manual", "La barre n'est pas tenue à la main.");
    const h = m.helm;
    if (body.course_deg != null) h.course_deg = wrap(body.course_deg);
    if (body.course_change_deg != null) h.course_deg = wrap(h.course_deg + body.course_change_deg);
    if (body.speed_kn != null) h.speed_kn = body.speed_kn;
    if (body.speed_change_kn != null) h.speed_kn = Math.min(28, Math.max(3, h.speed_kn + body.speed_change_kn));
    if (body.rudder != null) h.rudder = body.rudder;
    return { ...h };
  }

  listRecommendations(id: string): Recommendation[] {
    this.require("mission:play");
    const m = this.mission(id);
    if (m.stoppedAt_s !== null || m.acknowledgedAt_s !== null) return [];
    return [{ kind: "accuser", reason: "Le guide attend votre accusé de réception.", text: "ALL SHIPS CORPEN 020 SPEED 12" }];
  }

  // ------------------------------------------------------------------ orders
  submitOrder(id: string, body: SubmitOrder): OrderOutcome {
    this.require("command:submit");
    const m = this.running(id);
    const text = body.text.trim().toUpperCase();
    const parsed = parseOrder(text);
    if (!parsed) {
      return { accepted: false, refusal_reason: "Signal non reconnu.", hint: "Exemple : ALL SHIPS CORPEN 045 SPEED 12" };
    }
    if (body.mode === "direct") {
      this.apply(m, text);
      this.log("approved", { source: "keyboard", text_en: text, text_fr: parsed.fr }, { missionId: m.id });
      return { accepted: true, text_en: text, text_fr: parsed.fr, command_state: "dispatched" };
    }
    const command = this.createReviewCommand(m, text, parsed.fr, body.parent_id ?? null, "keyboard");
    return { accepted: true, command_id: command.id, command_state: command.state, text_en: text, text_fr: parsed.fr };
  }

  /** As `POST /v1/missions/{id}/voice`: the fake does not listen, it "hears" `heard`. */
  submitVoiceOrder(id: string, recording: Blob, parentId?: string): VoiceOrderOutcome {
    this.require("command:submit");
    const m = this.running(id);
    if (recording.size < MIN_RECORDING_BYTES) {
      throw new FakeError(422, "recording_rejected", "Enregistrement inutilisable : trop court, trop long ou format inconnu.");
    }
    const recordingId = `c-${String(++this.state.seq)}`;
    this.recordings.set(recordingId, recording);
    const heard = this.heard.trim().toUpperCase();
    const words = heard.split(/\s+/).map((word, i) => ({ word, confidence: i === 1 ? 0.42 : 0.97, start_s: i * 0.4, end_s: i * 0.4 + 0.35 }));
    const transcribed = { source: "voice", transcript: heard, audio: true, asr_model: "fake", parent_id: parentId ?? null };
    const parsed = parseOrder(heard);
    const base = { recording_id: recordingId, transcript: heard, heard_words: words, transcription_seconds: 0.8 };
    if (!parsed) {
      const refusal = "Signal non reconnu.";
      this.log("transcribed", { ...transcribed, refusal_reason: refusal }, { missionId: m.id, commandId: recordingId });
      return { ...base, accepted: false, refusal_reason: refusal, hint: "Exemple : ALL SHIPS CORPEN 045 SPEED 12" };
    }
    this.log("transcribed", transcribed, { missionId: m.id, commandId: recordingId });
    const command = this.createReviewCommand(m, heard, parsed.fr, parentId ?? null, "voice", recordingId);
    return { ...base, accepted: true, command_id: command.id, command_state: command.state, text_en: heard, text_fr: parsed.fr };
  }

  // ------------------------------------------------------------------ register
  readAudit({ missionId, afterSeq = 0, limit = 100 }: AuditQuery): AuditPage {
    this.require("audit:read");
    const events = this.state.audit.filter((e) => e.seq > afterSeq && (!missionId || e.mission_id === missionId)).slice(0, limit);
    return { events, next_after_seq: events.length === limit ? (events.at(-1)?.seq ?? null) : null };
  }

  verifyAudit(): AuditIntegrity {
    this.require("audit:read");
    const head = this.state.audit.at(-1)?.seq ?? null;
    return { intact: true, checked_events: this.state.audit.length, first_broken_seq: null, head_seq: head };
  }

  readRecording(commandId: string): Blob {
    this.require("audit:read");
    const recording = this.recordings.get(commandId);
    if (!recording) throw new FakeError(404, "recording_not_found", "Aucun enregistrement pour cette commande.");
    return recording;
  }

  simulateOrder(id: string, text: string): Simulation {
    this.require("command:submit");
    const m = this.running(id);
    const parsed = parseOrder(text.trim().toUpperCase());
    if (!parsed) return { accepted: false, refusal_reason: "Signal non reconnu." };
    const t = this.elapsed(m);
    const here = advance(m.leg, t);
    const course = this.nextCourse(m.leg.course_deg, parsed.course, text);
    const leg: Leg = { at_s: t, east_m: here.east, north_m: here.north, course_deg: course, speed_kn: parsed.speed ?? m.leg.speed_kn };
    const track = (i: number) =>
      Array.from({ length: 16 }, (_, k) => {
        const p = advance(leg, t + k * 60);
        return { at_s: t + k * 60, east_m: p.east - Math.sin(course * D2R) * SPACING_M * i, north_m: p.north - Math.cos(course * D2R) * SPACING_M * i };
      });
    const ships = m.scenario.playable_ships;
    return {
      accepted: true,
      text_fr: parsed.fr,
      recipients: ships.filter((s) => s !== m.scenario.guide_ship),
      track_by_ship: Object.fromEntries(ships.map((s, i) => [s, track(i)])),
      contact_cpas: [{ ship: m.player, contact_id: "TRK021", cpa_nm: 1.4, cpa_nm_without_order: 0.6, tcpa_s: 420, at_risk: false }],
      ships_passings: [],
    };
  }

  readCommand(commandId: string): Command {
    this.require("mission:play");
    const c = this.command(commandId);
    if (c.state === "dispatching" && c.dispatchAt !== null && this.now() >= c.dispatchAt) {
      c.state = "dispatched";
      c.dispatchAt = null;
      this.log("simulator_dispatched", { text_en: c.text_en }, { missionId: c.mission_id, commandId: c.id, actor: null });
      const m = this.state.missions.find((x) => x.id === c.mission_id);
      if (m?.stoppedAt_s === null) this.apply(m, c.text);
    }
    const command: Command & { dispatchAt?: number | null } = { ...c };
    delete command.dispatchAt;
    return command;
  }

  decideCommand(commandId: string, decision: CommandDecision): Command {
    this.require("command:decide");
    const c = this.command(commandId);
    const allowed = decision === "retry" ? c.state === "dispatch_failed" : c.state === "awaiting_review";
    if (!allowed) throw new FakeError(409, "invalid_transition", "Décision impossible dans cet état.");
    c.decided_by = this.state.session?.username ?? null;
    this.log(decision === "reject" ? "rejected" : "approved", { source: "review", decision, text_en: c.text_en }, {
      missionId: c.mission_id,
      commandId: c.id,
    });
    if (decision === "reject") c.state = "rejected";
    else {
      c.state = "dispatching";
      c.dispatchAt = this.now() + 800;
    }
    return this.readCommand(commandId);
  }

  // ------------------------------------------------------------------ doctrine
  askDoctrine(body: DoctrineQuestion): DoctrineAnswer {
    this.require("doctrine:ask");
    const allowed = this.listPublications();
    if (body.publication && !allowed.includes(body.publication)) {
      throw new FakeError(403, "publication_not_allowed", "Publication inconnue ou non autorisée pour ce rôle.");
    }
    const asked = body.question.toLowerCase();
    const passage = SAMPLE_PASSAGES.find(
      ({ citation: c, keywords }) =>
        allowed.includes(c.publication) &&
        (!body.publication || c.publication === body.publication) &&
        keywords.some((k) => asked.includes(k)),
    );
    const unknown = /\bRSA\b/.test(body.question) ? ["RSA"] : [];
    const common = {
      query_en: null,
      model: "fake",
      index_version: "fake-1",
      thresholds: { min_similarity: 0.45 },
      second_try: false,
      duration_ms: 900,
      unknown_terms: unknown,
      suggestions: unknown.length ? [{ unknown: "RSA", proposals: [{ term: "RAS", en: "replenishment at sea", fr: "ravitaillement à la mer" }] }] : [],
      trace_id: crypto.randomUUID(),
    };
    if (!passage) {
      this.log("doctrine_refused", { refusal_reason: "no_evidence" }, { missionId: null });
      return {
        ...common,
        status: "refused",
        answer: "Je ne trouve pas cette information dans les publications chargées.",
        refusal_reason: "no_evidence",
        refusal_detail: "aucun passage assez proche",
        citations: [],
      };
    }
    this.log("doctrine_answered", { citations: 1 }, { missionId: null });
    const { answer, citation } = passage;
    return { ...common, status: "answered", answer, refusal_reason: null, refusal_detail: null, citations: [citation] };
  }

  listPublications(): string[] {
    this.require("doctrine:ask");
    const classified = this.state.session?.permissions.includes("doctrine:classified") ?? false;
    return classified ? ["DEMO-MANUEL", "DEMO-RESTREINT"] : ["DEMO-MANUEL"];
  }

  searchGlossary(query: string): GlossaryResult {
    this.require("glossary:read");
    const q = query.trim().toLowerCase();
    return {
      query,
      entries: SAMPLE_GLOSSARY.filter((e) => q && [e.en, e.fr, e.abbreviation].some((v) => v?.toLowerCase().includes(q))),
    };
  }

  explainCommand(commandId: string): CommandExplanation {
    this.require("doctrine:ask");
    const c = this.command(commandId);
    return {
      command_id: c.id,
      explanation_en: `${c.text_en} The ordered values are taken as decoded.`,
      explanation_fr: `${c.text_fr} Les valeurs ordonnées sont reprises telles que décodées.`,
      source: "deterministic",
      citations: [],
      rejected_checks: [],
      model: "fake",
      duration_ms: 300,
    };
  }

  // ------------------------------------------------------------------ internals
  private createReviewCommand(
    m: MissionRecord,
    text: string,
    textFr: string,
    parentId: string | null,
    source: CommandSource,
    id = `c-${String(++this.state.seq)}`,
  ): CommandRecord {
    const command: CommandRecord = {
      id,
      mission_id: m.id,
      state: "awaiting_review",
      source,
      submitted_by: this.state.session?.username ?? "?",
      text,
      text_en: text,
      text_fr: textFr,
      parent_id: parentId,
      dispatchAt: null,
    };
    this.state.commands.push(command);
    this.log("awaiting_review", { source, text_en: text, text_fr: textFr, parent_id: parentId }, { missionId: m.id, commandId: id });
    return command;
  }

  private log(
    event: string,
    payload: Record<string, unknown>,
    where: { missionId: string | null; commandId?: string; actor?: string | null },
  ) {
    const last = this.state.audit.at(-1)?.seq ?? 0;
    this.state.audit.push({
      seq: last + 1,
      at: new Date(this.now()).toISOString(),
      actor_id: where.actor === undefined ? (this.state.session?.username ?? null) : where.actor,
      mission_id: where.missionId,
      command_id: where.commandId ?? null,
      event,
      payload,
    });
  }

  private mission(id: string): MissionRecord {
    const m = this.state.missions.find((x) => x.id === id);
    if (!m) throw new FakeError(404, "mission_not_found", "Mission inconnue.");
    return m;
  }

  private running(id: string): MissionRecord {
    const m = this.mission(id);
    if (m.stoppedAt_s !== null || this.elapsed(m) >= m.scenario.duration_s) {
      throw new FakeError(409, "mission_ended", "La mission est terminée.");
    }
    return m;
  }

  private command(id: string): CommandRecord {
    const c = this.state.commands.find((x) => x.id === id);
    if (!c) throw new FakeError(404, "command_not_found", "Commande inconnue.");
    return c;
  }

  private elapsed(m: MissionRecord): number {
    if (m.stoppedAt_s !== null) return m.stoppedAt_s;
    return Math.min(m.scenario.duration_s, Math.max(0, (this.now() - m.startedAt) / 1000));
  }

  private nextCourse(current: number, parsed: number | undefined, text: string) {
    if (parsed === undefined) return current;
    return /\bTURN\b/.test(text) ? wrap(current + parsed) : parsed;
  }

  private radio(m: MissionRecord, kind: string, sender: string, recipient: string, en: string, fr: string) {
    const id = (m.radio.at(-1)?.id ?? 0) + 1;
    m.radio = [...m.radio, { id, kind, sender, recipient, sent_at_s: this.elapsed(m), text_en: en, text_fr: fr }].slice(-40);
  }

  private apply(m: MissionRecord, text: string) {
    const parsed = parseOrder(text);
    if (!parsed) return;
    const t = this.elapsed(m);
    const here = advance(m.leg, t);
    m.leg = {
      at_s: t,
      east_m: here.east,
      north_m: here.north,
      course_deg: this.nextCourse(m.leg.course_deg, parsed.course, text),
      speed_kn: parsed.speed ?? m.leg.speed_kn,
    };
    m.pending = [];
    m.acknowledgedAt_s ??= t;
    this.radio(m, "joueur", m.player.toUpperCase(), "TOUS", text, parsed.fr);
  }

  private snapshot(m: MissionRecord): Mission {
    const t = this.elapsed(m);
    const ended = m.stoppedAt_s !== null || t >= m.scenario.duration_s;
    const guide = advance(m.leg, t);
    const course = m.leg.course_deg;
    const ships = m.scenario.playable_ships.map((name, i) => ({
      name,
      role: i === 0 ? "guide" : "escorte",
      east_m: guide.east - Math.sin(course * D2R) * SPACING_M * i,
      north_m: guide.north - Math.cos(course * D2R) * SPACING_M * i,
      heading_deg: course,
      speed_mps: m.leg.speed_kn * KN,
      status_for_player: name === m.player ? "Vous" : i === 0 ? "Guide" : "En station",
      status_for_fleet: i === 0 ? "Guide" : "En station",
    }));
    const me = ships.find((s) => s.name === m.player) ?? ships[0]!;
    const contact = { east: 3900 - Math.sin(55 * D2R) * 16 * KN * t, north: 3300 - Math.cos(55 * D2R) * 16 * KN * t };
    const dx = contact.east - me.east_m;
    const dy = contact.north - me.north_m;
    const objectives: Objective[] = [
      { description: "Accuser l'ordre du guide", achieved: m.acknowledgedAt_s !== null, achieved_at_s: m.acknowledgedAt_s, deadline_s: 300 },
      { description: "Classer la piste TRK021", achieved: m.classification === "hostile", achieved_at_s: m.classification === "hostile" ? m.classifiedAt_s : null },
    ];
    const reached = objectives.filter((o) => o.achieved).length;
    const isGuide = m.player === m.scenario.guide_ship;
    const index = m.scenario.playable_ships.indexOf(m.player);
    return {
      id: m.id,
      scenario_id: m.scenario.id,
      title: m.scenario.title,
      phase: ended ? "ended" : "running",
      elapsed_s: t,
      duration_s: m.scenario.duration_s,
      player_ship: m.player,
      guide_ship: m.scenario.guide_ship,
      guide_course_deg: course,
      guide_speed_kn: m.leg.speed_kn,
      formation: "column",
      autopilot: m.autopilot,
      manual_helm: m.manualHelm,
      helm: { ...m.helm },
      ships,
      contacts: [
        {
          id: "TRK021",
          category: "Surface",
          classification: m.classification,
          course_deg: 235,
          speed_kn: 16,
          east_m: contact.east,
          north_m: contact.north,
          range_nm: Math.hypot(dx, dy) / NM,
          bearing_deg: wrap(Math.atan2(dx, dy) / D2R),
          cpa_nm: 0.8,
          tcpa_min: 9,
        },
      ],
      radio_messages: m.radio,
      objectives,
      authorization_requests: m.requests,
      pending_orders: m.pending,
      planned_orders: [{ planned_at_s: 120, text_en: "ALL SHIPS TURN 30 STBD", text_fr: "À tous : venir de 30° sur tribord" }],
      reconnaissance_target_by_ship: {},
      station: isGuide
        ? null
        : {
            east_m: guide.east - Math.sin(course * D2R) * SPACING_M * index,
            north_m: guide.north - Math.cos(course * D2R) * SPACING_M * index,
            offset_m: 0,
          },
      debrief: ended
        ? {
            score: reached * 50,
            objectives,
            objectives_total: objectives.length,
            classification_by_contact: { TRK021: { chosen: m.classification, actual: "hostile" } },
            closest_cpa_nm_by_contact: { TRK021: 0.8 },
            closest_ships_distance_m: SPACING_M,
          }
        : null,
    };
  }
}
