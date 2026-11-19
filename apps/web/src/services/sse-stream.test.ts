import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FakeBackend } from "../mocks/fake-backend";
import type { Mission, StreamEvent, StreamStatus } from "../socle/ports";
import { SseStream } from "./sse-stream";

class FakeEventSource {
  static last: FakeEventSource | null = null;
  readyState = 1;
  onerror: (() => void) | null = null;
  closed = false;
  private readonly listeners = new Map<string, (m: MessageEvent<string>) => void>();

  constructor(readonly url: string) {
    FakeEventSource.last = this;
  }
  addEventListener(type: string, listener: (m: MessageEvent<string>) => void) {
    this.listeners.set(type, listener);
  }
  emit(type: string, data: string) {
    this.listeners.get(type)?.(new MessageEvent(type, { data }));
  }
  fail(closed: boolean) {
    this.readyState = closed ? 2 : 0;
    this.onerror?.();
  }
  close() {
    this.closed = true;
  }
}

describe("SseStream", () => {
  let mission: Mission;
  let events: StreamEvent[];
  let statuses: StreamStatus[];
  const readMission = vi.fn<(id: string) => Promise<Mission>>();

  beforeEach(() => {
    vi.useFakeTimers();
    const backend = new FakeBackend();
    backend.signIn("instructeur", "demo");
    mission = backend.startMission({ scenario_id: "transit-colonne", player_ship: "alfa", autopilot: false, manual_helm: false });
    readMission.mockReset().mockResolvedValue(mission);
    events = [];
    statuses = [];
  });
  afterEach(() => vi.useRealTimers());

  const subscribe = () =>
    new SseStream({ readMission }, { eventSource: (url) => new FakeEventSource(url) as unknown as EventSource }).subscribe("m 1", {
      onEvent: (e) => events.push(e),
      onStatus: (s) => statuses.push(s),
    });

  it("goes live on the first situation and closes once the mission ends", () => {
    subscribe();
    const es = FakeEventSource.last!;
    expect(es.url).toBe("/v1/missions/m%201/events");
    es.emit("situation", JSON.stringify(mission));
    es.emit("phase", JSON.stringify({ phase: "ended" }));
    expect(statuses).toEqual(["connecting", "live", "closed"]);
    expect(events.map((e) => e.type)).toEqual(["situation", "phase"]);
    expect(es.closed).toBe(true);
  });

  it("falls back to polling while the stream is down, then reopens it", async () => {
    subscribe();
    const first = FakeEventSource.last!;
    first.fail(true);
    expect(statuses.at(-1)).toBe("polling");
    await vi.advanceTimersByTimeAsync(2000);
    expect(readMission).toHaveBeenCalledWith("m 1");
    expect(events.at(-1)).toEqual({ type: "situation", mission });
    await vi.advanceTimersByTimeAsync(3000);
    expect(FakeEventSource.last).not.toBe(first);
  });

  it("ignores a malformed frame", () => {
    subscribe();
    FakeEventSource.last!.emit("situation", "{oops");
    expect(events).toEqual([]);
  });

  it("stops everything on unsubscribe", async () => {
    const unsubscribe = subscribe();
    FakeEventSource.last!.fail(false);
    unsubscribe();
    await vi.advanceTimersByTimeAsync(10_000);
    expect(readMission).not.toHaveBeenCalled();
    expect(statuses.at(-1)).toBe("closed");
  });
});
