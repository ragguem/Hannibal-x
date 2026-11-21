import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useApi } from "../../socle/composition";
import type { StartMission } from "../../socle/ports";
import { queryKeys } from "../../socle/query-keys";

export function useScenarios() {
  const api = useApi();
  return useQuery({ queryKey: queryKeys.scenarios, queryFn: () => api.listScenarios(), staleTime: 5 * 60_000 });
}

/** The back-office plans then launches; the console then reads the mission from `apps/api`. */
export function useStartMission() {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: StartMission) => api.startMission(body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.missionHistory }),
  });
}

export function useMissionHistory() {
  const api = useApi();
  return useInfiniteQuery({
    queryKey: queryKeys.missionHistory,
    queryFn: ({ pageParam }) => api.listMissionHistory(pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor ?? undefined,
  });
}

export function useArchiveMission() {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (missionId: string) => api.archiveMission(missionId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.missionHistory }),
  });
}
