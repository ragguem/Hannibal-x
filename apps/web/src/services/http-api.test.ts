import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { FakeBackend } from "../mocks/fake-backend";
import { createHandlers } from "../mocks/handlers";
import { isApiError } from "./api-error";
import { HttpApi } from "./http-api";

const backend = new FakeBackend();
const server = setupServer(...createHandlers(backend));
const api = new HttpApi("http://hx.test");

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  backend.state = { session: null, missions: [], commands: [], audit: [], seq: 0 };
});
afterAll(() => server.close());

describe("HttpApi against the contract mocks", () => {
  it("reads a missing session as null rather than an error", async () => {
    expect(await api.readSession()).toBeNull();
  });

  it("maps an error body onto ApiError", async () => {
    const error: unknown = await api.signIn({ username: "instructeur", password: "x" }).catch((e: unknown) => e);
    expect(isApiError(error) && error.status).toBe(401);
    expect(isApiError(error) && error.code).toBe("invalid_credentials");
  });

  it("runs a review order through to dispatch", async () => {
    await api.signIn({ username: "instructeur", password: "demo" });
    const mission = await api.startMission({ scenario_id: "transit-colonne", player_ship: "alfa", autopilot: false, manual_helm: false });
    const outcome = await api.submitOrder(mission.id, { text: "ALL SHIPS CORPEN 045", mode: "review" });
    expect(outcome).toMatchObject({ accepted: true, command_state: "awaiting_review" });
    const command = await api.decideCommand(outcome.command_id!, "approve");
    expect(command.state).toBe("dispatching");
    await api.stopMission(mission.id);
    expect((await api.readMission(mission.id)).phase).toBe("ended");
  });

  it("reports an unreachable server as a network error", async () => {
    const offline = new HttpApi("http://hx.test", () => Promise.reject(new TypeError("Failed to fetch")));
    const error: unknown = await offline.listScenarios().catch((e: unknown) => e);
    expect(isApiError(error) && error.status).toBe(0);
  });
});
