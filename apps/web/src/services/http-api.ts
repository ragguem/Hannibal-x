import createClient from "openapi-fetch";
import type { ApiPort, SessionView, SignIn } from "../socle/ports";
import { networkError, toApiError } from "./api-error";
import type { paths } from "./openapi";

interface FetchResult<T> {
  data?: T;
  error?: unknown;
  response: Response;
}

async function call<T>(request: () => Promise<FetchResult<T>>): Promise<T> {
  let result: FetchResult<T>;
  try {
    result = await request();
  } catch (cause) {
    throw networkError(cause);
  }
  if (!result.response.ok) throw toApiError(result.response.status, result.error);
  return result.data as T;
}

/** ApiPort over HTTP: the typed OpenAPI client for the API, plain fetch for the back-office session. */
export class HttpApi implements ApiPort {
  private readonly client: ReturnType<typeof createClient<paths>>;

  constructor(
    private readonly baseUrl = "",
    private readonly fetcher: typeof fetch = (...args) => globalThis.fetch(...args),
  ) {
    this.client = createClient<paths>({ baseUrl, credentials: "same-origin", fetch: fetcher });
  }

  private async session<T>(method: "GET" | "POST" | "DELETE", body?: SignIn): Promise<T | null> {
    let response: Response;
    try {
      response = await this.fetcher(`${this.baseUrl}/v1/session`, {
        method,
        credentials: "same-origin",
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      });
    } catch (cause) {
      throw networkError(cause);
    }
    if (method === "GET" && response.status === 401) return null;
    const payload: unknown = response.status === 204 ? null : await response.json().catch(() => null);
    if (!response.ok) throw toApiError(response.status, payload);
    return payload as T;
  }

  readSession = () => this.session<SessionView>("GET");

  signIn = async (body: SignIn) => {
    const session = await this.session<SessionView>("POST", body);
    if (!session) throw toApiError(502, null);
    return session;
  };

  signOut = async () => {
    await this.session("DELETE");
  };

  listScenarios = () => call(() => this.client.GET("/v1/scenarios"));

  startMission: ApiPort["startMission"] = (body) => call(() => this.client.POST("/v1/missions", { body }));

  readMission = (missionId: string) =>
    call(() => this.client.GET("/v1/missions/{mission_id}", { params: { path: { mission_id: missionId } } }));

  stopMission = async (missionId: string) => {
    await call(() => this.client.DELETE("/v1/missions/{mission_id}", { params: { path: { mission_id: missionId } } }));
  };

  submitOrder: ApiPort["submitOrder"] = (missionId, body) =>
    call(() => this.client.POST("/v1/missions/{mission_id}/orders", { params: { path: { mission_id: missionId } }, body }));

  simulateOrder = (missionId: string, text: string) =>
    call(() =>
      this.client.POST("/v1/missions/{mission_id}/simulations", { params: { path: { mission_id: missionId } }, body: { text } }),
    );

  readCommand = (commandId: string) =>
    call(() => this.client.GET("/v1/commands/{command_id}", { params: { path: { command_id: commandId } } }));

  decideCommand: ApiPort["decideCommand"] = (commandId, decision) =>
    call(() =>
      this.client.POST("/v1/commands/{command_id}/decision", { params: { path: { command_id: commandId } }, body: { decision } }),
    );

  listRecommendations = (missionId: string) =>
    call(() =>
      this.client.GET("/v1/missions/{mission_id}/recommendations", { params: { path: { mission_id: missionId } } }),
    );

  setHelm: ApiPort["setHelm"] = (missionId, body) =>
    call(() => this.client.POST("/v1/missions/{mission_id}/helm", { params: { path: { mission_id: missionId } }, body }));

  classifyContact: ApiPort["classifyContact"] = async (missionId, contactId, classification) => {
    await call(() =>
      this.client.POST("/v1/missions/{mission_id}/contacts/{contact_id}/classification", {
        params: { path: { mission_id: missionId, contact_id: contactId } },
        body: { classification },
      }),
    );
  };

  replyRequest: ApiPort["replyRequest"] = async (missionId, ship, approve) => {
    await call(() =>
      this.client.POST("/v1/missions/{mission_id}/requests/{ship}/reply", {
        params: { path: { mission_id: missionId, ship } },
        body: { approve },
      }),
    );
  };

  setAutopilot: ApiPort["setAutopilot"] = async (missionId, enabled) => {
    await call(() =>
      this.client.PUT("/v1/missions/{mission_id}/autopilot", {
        params: { path: { mission_id: missionId } },
        body: { enabled },
      }),
    );
  };

  submitVoiceOrder: ApiPort["submitVoiceOrder"] = (missionId, recording, parentId) => {
    const form = new FormData();
    form.append("audio", recording, recording.type === "audio/wav" ? "ordre.wav" : "ordre");
    if (parentId) form.append("parent_id", parentId);
    return call(() =>
      this.client.POST("/v1/missions/{mission_id}/voice", {
        params: { path: { mission_id: missionId } },
        // The browser sets the multipart boundary itself: the body goes out untouched.
        body: form as never,
        bodySerializer: () => form,
      }),
    );
  };

  readAudit: ApiPort["readAudit"] = ({ missionId, afterSeq, limit }) =>
    call(() =>
      this.client.GET("/v1/audit", {
        params: { query: { mission_id: missionId === "" ? undefined : missionId, after_seq: afterSeq, limit } },
      }),
    );

  verifyAudit = () => call(() => this.client.GET("/v1/audit/integrity"));

  recordingUrl = (commandId: string) => `${this.baseUrl}/v1/audit/${encodeURIComponent(commandId)}/audio`;
}
