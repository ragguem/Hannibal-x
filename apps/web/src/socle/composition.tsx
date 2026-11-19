import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import { createContext, use, useState, type ReactNode } from "react";
import { HttpApi } from "../services/http-api";
import { SseStream } from "../services/sse-stream";
import type { ApiPort, StreamPort } from "./ports";
import { createQueryClient } from "./query-client";

export interface Ports {
  api: ApiPort;
  stream: StreamPort;
}

/** The only place adapters are built. Tests pass their own ports instead. */
export function createPorts(): Ports {
  const api = new HttpApi();
  return { api, stream: new SseStream(api) };
}

const ApiContext = createContext<ApiPort | null>(null);
const StreamContext = createContext<StreamPort | null>(null);

interface CompositionProps {
  children: ReactNode;
  ports?: Ports;
  queryClient?: QueryClient;
}

export function Composition({ children, ports, queryClient }: CompositionProps) {
  const [resolvedPorts] = useState(() => ports ?? createPorts());
  const [client] = useState(() => queryClient ?? createQueryClient());
  return (
    <QueryClientProvider client={client}>
      <ApiContext value={resolvedPorts.api}>
        <StreamContext value={resolvedPorts.stream}>{children}</StreamContext>
      </ApiContext>
    </QueryClientProvider>
  );
}

export function useApi(): ApiPort {
  const api = use(ApiContext);
  if (!api) throw new Error("useApi doit être appelé sous <Composition>.");
  return api;
}

export function useStream(): StreamPort {
  const stream = use(StreamContext);
  if (!stream) throw new Error("useStream doit être appelé sous <Composition>.");
  return stream;
}
