import type { ApiPort, Mission, MissionPhase, StreamHandlers, StreamPort } from "../socle/ports";

type EventSourceFactory = (url: string) => EventSource;

const EVENT_SOURCE_CLOSED = 2;

export interface SseStreamOptions {
  baseUrl?: string;
  pollMs?: number;
  /** A closed EventSource (HTTP error) is not retried by the browser: reopen it after this delay. */
  reopenMs?: number;
  eventSource?: EventSourceFactory;
}

/**
 * StreamPort over `GET /v1/missions/{id}/events` (`situation` every 0.25 s, then `phase`).
 * While the stream is down the mission is re-read every 2 s, so the console never freezes.
 */
export class SseStream implements StreamPort {
  private readonly baseUrl: string;
  private readonly pollMs: number;
  private readonly reopenMs: number;
  private readonly open: EventSourceFactory;

  constructor(
    private readonly api: Pick<ApiPort, "readMission">,
    options: SseStreamOptions = {},
  ) {
    this.baseUrl = options.baseUrl ?? "";
    this.pollMs = options.pollMs ?? 2000;
    this.reopenMs = options.reopenMs ?? 5000;
    this.open = options.eventSource ?? ((url) => new EventSource(url, { withCredentials: true }));
  }

  subscribe(missionId: string, { onEvent, onStatus }: StreamHandlers): () => void {
    const url = `${this.baseUrl}/v1/missions/${encodeURIComponent(missionId)}/events`;
    let closed = false;
    let source: EventSource | null = null;
    let poll: ReturnType<typeof setInterval> | null = null;
    let reopen: ReturnType<typeof setTimeout> | null = null;

    const stopPolling = () => {
      if (poll !== null) clearInterval(poll);
      poll = null;
    };

    const close = () => {
      if (closed) return;
      closed = true;
      stopPolling();
      if (reopen !== null) clearTimeout(reopen);
      source?.close();
      source = null;
      onStatus("closed");
    };

    const end = (phase: MissionPhase) => {
      onEvent({ type: "phase", phase });
      if (phase === "ended") close();
    };

    const readOnce = async () => {
      try {
        const mission = await this.api.readMission(missionId);
        if (closed) return;
        onEvent({ type: "situation", mission });
        if (mission.phase === "ended") end("ended");
      } catch {
        // Next tick retries; a 401 is handled by the query layer on its own reads.
      }
    };

    const startPolling = () => {
      if (closed || poll !== null) return;
      onStatus("polling");
      poll = setInterval(() => void readOnce(), this.pollMs);
    };

    const connect = () => {
      if (closed) return;
      const es = this.open(url);
      source = es;
      es.addEventListener("situation", (message) => {
        let mission: Mission;
        try {
          mission = JSON.parse((message as MessageEvent<string>).data) as Mission;
        } catch {
          return;
        }
        if (closed) return;
        if (poll !== null) stopPolling();
        onStatus("live");
        onEvent({ type: "situation", mission });
      });
      es.addEventListener("phase", (message) => {
        try {
          const { phase } = JSON.parse((message as MessageEvent<string>).data) as { phase: MissionPhase };
          end(phase);
        } catch {
          // Malformed frame: ignore, the next situation carries the phase anyway.
        }
      });
      es.onerror = () => {
        if (closed) return;
        startPolling();
        if (es.readyState === EVENT_SOURCE_CLOSED) {
          source = null;
          reopen = setTimeout(connect, this.reopenMs);
        }
      };
    };

    onStatus("connecting");
    connect();
    return close;
  }
}
