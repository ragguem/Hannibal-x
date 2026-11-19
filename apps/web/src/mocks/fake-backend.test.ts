import { describe, expect, it } from "vitest";
import { FakeBackend, FakeError } from "./fake-backend";

const start = (now: { t: number }) => {
  const backend = new FakeBackend(() => now.t);
  backend.signIn("instructeur", "demo");
  const mission = backend.startMission({ scenario_id: "transit-colonne", player_ship: "alfa", autopilot: false, manual_helm: true });
  return { backend, id: mission.id };
};

describe("FakeBackend", () => {
  it("dispatches an approved command after its delay and applies it", () => {
    const now = { t: 0 };
    const { backend, id } = start(now);
    const outcome = backend.submitOrder(id, { text: "all ships corpen 090 speed 15", mode: "review" });
    expect(backend.decideCommand(outcome.command_id!, "approve").state).toBe("dispatching");
    now.t = 1000;
    expect(backend.readCommand(outcome.command_id!).state).toBe("dispatched");
    const mission = backend.readMission(id);
    expect(mission.guide_course_deg).toBe(90);
    expect(mission.objectives[0]!.achieved).toBe(true);
    expect(mission.radio_messages.at(-1)!.sender).toBe("ALFA");
  });

  it("refuses a second decision", () => {
    const { backend, id } = start({ t: 0 });
    const outcome = backend.submitOrder(id, { text: "ALL SHIPS TURN 30 STBD", mode: "review" });
    backend.decideCommand(outcome.command_id!, "reject");
    expect(() => backend.decideCommand(outcome.command_id!, "approve")).toThrow(FakeError);
  });

  it("keeps the manual helm within the speed limits", () => {
    const { backend, id } = start({ t: 0 });
    expect(backend.setHelm(id, { speed_change_kn: 40 }).speed_kn).toBe(28);
    expect(backend.setHelm(id, { course_change_deg: -30 }).course_deg).toBe(350);
  });

  it("ends with a debrief and refuses further orders", () => {
    const { backend, id } = start({ t: 0 });
    backend.classifyContact(id, "TRK021", "hostile");
    backend.stopMission(id);
    const mission = backend.readMission(id);
    expect(mission.phase).toBe("ended");
    expect(mission.debrief).toMatchObject({ score: 50, objectives_total: 2 });
    expect(() => backend.submitOrder(id, { text: "ALL SHIPS SPEED 10", mode: "direct" })).toThrow(FakeError);
  });

  it("requires a session", () => {
    expect(() => new FakeBackend().listScenarios()).toThrow(FakeError);
  });
});
