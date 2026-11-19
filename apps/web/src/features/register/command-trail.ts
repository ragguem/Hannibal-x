import type { AuditEventView } from "../../socle/ports";

export const EVENT_LABEL: Record<string, string> = {
  mission_started: "mission lancée",
  mission_finished: "mission terminée",
  transcribed: "transcrit",
  awaiting_review: "en attente de validation",
  approved: "approuvé",
  rejected: "rejeté",
  simulator_dispatched: "transmis au simulateur",
  dispatch_retry: "nouvelle tentative",
  dispatch_failed: "échec de transmission",
  helm: "barre",
  contact_classified: "piste classée",
  doctrine: "question de doctrine",
};

export type TrailOutcome = "pending" | "approved" | "rejected" | "dispatched" | "failed" | "refused" | "logged";

export const OUTCOME_LABEL: Record<TrailOutcome, string> = {
  pending: "en attente",
  approved: "approuvé",
  rejected: "rejeté",
  dispatched: "transmis",
  failed: "échec d'envoi",
  refused: "non reconnu",
  logged: "consigné",
};

/** One register line: a command and everything that happened to it, or a lone event (mission, helm…). */
export interface CommandTrail {
  key: string;
  commandId: string | null;
  missionId: string | null;
  actor: string | null;
  source: string | null;
  heard: string | null;
  textEn: string | null;
  textFr: string | null;
  refusalReason: string | null;
  parentId: string | null;
  hasRecording: boolean;
  outcome: TrailOutcome;
  /** Lot 5: status of the doctrine check attached to the command, when there is one. */
  doctrineStatus: string | null;
  events: { seq: number; at: string; event: string; actor: string | null }[];
  firstAt: string;
}

const text = (value: unknown): string | null => (typeof value === "string" && value !== "" ? value : null);

const OUTCOME_BY_EVENT: Partial<Record<string, TrailOutcome>> = {
  awaiting_review: "pending",
  approved: "approved",
  rejected: "rejected",
  simulator_dispatched: "dispatched",
  dispatch_failed: "failed",
};

function newTrail(event: AuditEventView): CommandTrail {
  return {
    key: event.command_id ?? `seq-${String(event.seq)}`,
    commandId: event.command_id ?? null,
    missionId: event.mission_id ?? null,
    actor: event.actor_id,
    source: null,
    heard: null,
    textEn: null,
    textFr: null,
    refusalReason: null,
    parentId: null,
    hasRecording: false,
    outcome: "logged",
    doctrineStatus: null,
    events: [],
    firstAt: event.at,
  };
}

function absorb(trail: CommandTrail, event: AuditEventView) {
  const p = event.payload;
  trail.events.push({ seq: event.seq, at: event.at, event: event.event, actor: event.actor_id });
  trail.source ??= text(p.source);
  trail.heard ??= text(p.transcript);
  trail.textEn = text(p.text_en) ?? trail.textEn;
  trail.textFr = text(p.text_fr) ?? trail.textFr;
  trail.parentId ??= text(p.parent_id);
  trail.refusalReason = text(p.refusal_reason) ?? trail.refusalReason;
  if (p.audio === true) trail.hasRecording = true;
  if (event.event === "doctrine") trail.doctrineStatus = text(p.status);
  const outcome = OUTCOME_BY_EVENT[event.event];
  if (outcome) trail.outcome = outcome;
  else if (trail.refusalReason && trail.outcome === "logged") trail.outcome = "refused";
}

/** Groups events by command (events arrive in `seq` order); newest line first. */
export function groupByCommand(events: readonly AuditEventView[]): CommandTrail[] {
  const byKey = new Map<string, CommandTrail>();
  for (const event of events) {
    const key = event.command_id ?? `seq-${String(event.seq)}`;
    let trail = byKey.get(key);
    if (!trail) {
      trail = newTrail(event);
      byKey.set(key, trail);
    }
    absorb(trail, event);
  }
  return [...byKey.values()].reverse();
}

export interface TrailFilter {
  source: "all" | "voice" | "keyboard";
  outcome: "all" | TrailOutcome;
  search: string;
}

export function filterTrails(trails: readonly CommandTrail[], filter: TrailFilter): CommandTrail[] {
  const needle = filter.search.trim().toLowerCase();
  return trails.filter(
    (t) =>
      (filter.source === "all" || t.source === filter.source) &&
      (filter.outcome === "all" || t.outcome === filter.outcome) &&
      (needle === "" ||
        [t.heard, t.textEn, t.textFr, t.actor, t.commandId].some((v) => v?.toLowerCase().includes(needle))),
  );
}
