import { describe, expect, it } from "vitest";
import type { AuditEventView } from "../../socle/ports";
import { filterTrails, groupByCommand } from "./command-trail";

let seq = 0;
const event = (name: string, commandId: string | null, payload: Record<string, unknown> = {}): AuditEventView => ({
  seq: ++seq,
  at: "2026-11-19T10:00:00Z",
  actor_id: "instructeur",
  mission_id: "m-1",
  command_id: commandId,
  event: name,
  payload,
});

describe("groupByCommand", () => {
  const events = [
    event("mission_started", null),
    event("transcribed", "c-1", { source: "voice", transcript: "ALL SHIPS CORPEN 045", audio: true }),
    event("awaiting_review", "c-1", { source: "voice", text_en: "ALL SHIPS CORPEN 045", text_fr: "cap 045" }),
    event("transcribed", "c-2", { source: "voice", transcript: "GOOD MORNING", audio: true, refusal_reason: "Signal non reconnu." }),
    event("approved", "c-1", { decision: "approve" }),
    event("simulator_dispatched", "c-1"),
  ];

  it("follows each command to its last outcome, newest line first", () => {
    const [refused, dispatched, mission] = groupByCommand(events);
    expect(refused).toMatchObject({ commandId: "c-2", outcome: "refused", hasRecording: true, heard: "GOOD MORNING" });
    expect(dispatched).toMatchObject({ commandId: "c-1", outcome: "dispatched", source: "voice", textFr: "cap 045" });
    expect(dispatched!.events.map((e) => e.event)).toEqual(["transcribed", "awaiting_review", "approved", "simulator_dispatched"]);
    expect(mission).toMatchObject({ commandId: null, outcome: "logged" });
  });

  it("filters by source, outcome and text", () => {
    const trails = groupByCommand(events);
    expect(filterTrails(trails, { source: "voice", outcome: "all", search: "" })).toHaveLength(2);
    expect(filterTrails(trails, { source: "all", outcome: "refused", search: "" })).toHaveLength(1);
    expect(filterTrails(trails, { source: "all", outcome: "all", search: "cap 045" })[0]?.commandId).toBe("c-1");
  });
});
