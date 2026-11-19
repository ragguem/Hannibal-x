import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useApi, useStream } from "../../socle/composition";
import type { Classification, Mission, SetHelm, StreamStatus } from "../../socle/ports";
import { queryKeys } from "../../socle/query-keys";

/** The situation, written by the stream; the GET only serves the first paint and the 2 s fallback. */
export function useMission(missionId: string) {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.mission(missionId),
    queryFn: () => api.readMission(missionId),
    staleTime: Number.POSITIVE_INFINITY,
  });
}

/**
 * Subscribes once per console. `setQueryData` keeps structural sharing, so unchanged slices
 * (objectives, radio log…) keep their reference and memoized panels skip the 4 Hz re-render.
 */
export function useMissionStream(missionId: string): StreamStatus {
  const stream = useStream();
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<StreamStatus>("connecting");

  useEffect(() => {
    const key = queryKeys.mission(missionId);
    return stream.subscribe(missionId, {
      onEvent: (event) => {
        if (event.type === "situation") {
          queryClient.setQueryData(key, event.mission);
          return;
        }
        queryClient.setQueryData<Mission>(key, (m) => (m ? { ...m, phase: event.phase } : m));
        if (event.phase === "ended") void queryClient.invalidateQueries({ queryKey: key });
      },
      onStatus: setStatus,
    });
  }, [missionId, stream, queryClient]);

  return status;
}

/** Mutations on the running mission. Toggles are optimistic; the next situation confirms them. */
export function useMissionActions(missionId: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  const key = queryKeys.mission(missionId);

  const patch = async (change: (m: Mission) => Mission) => {
    await queryClient.cancelQueries({ queryKey: key });
    const previous = queryClient.getQueryData<Mission>(key);
    if (previous) queryClient.setQueryData(key, change(previous));
    return { previous };
  };
  const rollback = (_e: unknown, _v: unknown, context: { previous: Mission | undefined } | undefined) => {
    if (context?.previous) queryClient.setQueryData(key, context.previous);
  };
  const refresh = () => queryClient.invalidateQueries({ queryKey: key });

  const stop = useMutation({ mutationFn: () => api.stopMission(missionId), onSuccess: refresh });

  const autopilot = useMutation({
    mutationFn: (enabled: boolean) => api.setAutopilot(missionId, enabled),
    onMutate: (enabled) => patch((m) => ({ ...m, autopilot: enabled })),
    onError: rollback,
  });

  const classify = useMutation({
    mutationFn: ({ contactId, classification }: { contactId: string; classification: Classification }) =>
      api.classifyContact(missionId, contactId, classification),
    onMutate: ({ contactId, classification }) =>
      patch((m) => ({ ...m, contacts: m.contacts.map((c) => (c.id === contactId ? { ...c, classification } : c)) })),
    onError: rollback,
  });

  const reply = useMutation({
    mutationFn: ({ ship, approve }: { ship: string; approve: boolean }) => api.replyRequest(missionId, ship, approve),
    onMutate: ({ ship }) =>
      patch((m) => ({ ...m, authorization_requests: m.authorization_requests.filter((r) => r.ship !== ship) })),
    onError: rollback,
  });

  const helm = useMutation({
    mutationFn: (body: SetHelm) => api.setHelm(missionId, body),
    onSuccess: (h) => queryClient.setQueryData<Mission>(key, (m) => (m ? { ...m, helm: h } : m)),
  });

  return { stop, autopilot, classify, reply, helm };
}
