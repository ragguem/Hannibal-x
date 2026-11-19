import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";
import { isApiError } from "../services/api-error";
import { queryKeys } from "./query-keys";

const MAX_RETRIES = 2;

/** 4xx are answers, not incidents: retrying them only delays the message. */
export const shouldRetry = (failureCount: number, error: unknown): boolean =>
  failureCount < MAX_RETRIES && !(isApiError(error) && error.status >= 400 && error.status < 500);

export function createQueryClient(): QueryClient {
  // An expired session anywhere sends the operator back to sign-in (RequireSession reacts to `null`)
  // without touching the mission cache, so nothing is lost if they sign in again.
  const onError = (error: unknown) => {
    if (isApiError(error) && error.status === 401) client.setQueryData(queryKeys.session, null);
  };
  const client: QueryClient = new QueryClient({
    queryCache: new QueryCache({ onError }),
    mutationCache: new MutationCache({ onError }),
    defaultOptions: {
      queries: { retry: shouldRetry, refetchOnWindowFocus: false, staleTime: 30_000 },
      mutations: { retry: false },
    },
  });
  return client;
}
