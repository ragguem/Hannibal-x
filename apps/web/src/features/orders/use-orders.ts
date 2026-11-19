import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useApi } from "../../socle/composition";
import type { CommandDecision, CommandState, SubmitOrder } from "../../socle/ports";
import { queryKeys } from "../../socle/query-keys";

export function useSubmitOrder(missionId: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: SubmitOrder) => api.submitOrder(missionId, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.recommendations(missionId) }),
  });
}

export function useSimulateOrder(missionId: string) {
  const api = useApi();
  return useMutation({ mutationFn: (text: string) => api.simulateOrder(missionId, text) });
}

/** The stream carries no command events: poll while the command can still change. */
const POLL_MS: Partial<Record<CommandState, number>> = { awaiting_review: 2000, dispatching: 1000 };

export function useCommand(commandId: string | null) {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.command(commandId ?? ""),
    queryFn: () => api.readCommand(commandId ?? ""),
    enabled: commandId !== null,
    refetchInterval: (query) => (query.state.data ? (POLL_MS[query.state.data.state] ?? false) : false),
  });
}

export function useDecideCommand() {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ commandId, decision }: { commandId: string; decision: CommandDecision }) =>
      api.decideCommand(commandId, decision),
    onSuccess: (command) => queryClient.setQueryData(queryKeys.command(command.id), command),
  });
}
