import type {
  AuthorizationRequest,
  Classification,
  Command,
  CommandDecision,
  Mission,
  Objective,
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
    duration_s: 1200,
    guide_ship: "hannibal",
    playable_ships: ["hannibal", "alfa", "charlie"],
  },
];

const ACCOUNTS: Record<string, { password: string; role: string; permissions: string[] }> = {
  instructeur: {
    password: "demo",
    role: "instructeur",
    permissions: ["mission:play", "command:submit", "command:decide", "audit:read", "user:manage"],
  },
  eleve: { password: "demo", role: "eleve", permissions: ["mission:play", "command:submit"] },
};

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
  seq: number;
}

export class FakeError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

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
  state: FakeState = { session: null, missions: [], commands: [], seq: 0 };

  constructor(private readonly now: () => number = () => Date.now()) {}

  // ------------------------------------------------------------------ session
  readSession(): SessionView | null {
    return this.state.session;
  }

  signIn(username: string, password: string): SessionView {
    const account = ACCOUNTS[username];
    if (account?.password !== password) throw new FakeError(401, "invalid_credentials", "Identifiants invalides.");
    const expires = new Date(this.now() + 8 * 3600_000).toISOString();
    this.state.session = { username, role: account.role, permissions: account.permissions, expires_at: expires };
    return this.state.session;
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
      return { accepted: true, text_en: text, text_fr: parsed.fr, command_state: "dispatched" };
    }
    const command: CommandRecord = {
      id: `c-${String(++this.state.seq)}`,
      mission_id: m.id,
      state: "awaiting_review",
      submitted_by: this.state.session?.username ?? "?",
      text,
      text_en: text,
      text_fr: parsed.fr,
      parent_id: body.parent_id ?? null,
      dispatchAt: null,
    };
    this.state.commands.push(command);
    return { accepted: true, command_id: command.id, command_state: command.state, text_en: text, text_fr: parsed.fr };
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
    if (decision === "reject") c.state = "rejected";
    else {
      c.state = "dispatching";
      c.dispatchAt = this.now() + 800;
    }
    return this.readCommand(commandId);
  }

  // ------------------------------------------------------------------ internals
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
