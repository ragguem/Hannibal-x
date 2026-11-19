import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useApi } from "../../socle/composition";
import { queryKeys } from "../../socle/query-keys";

export function useSubmitVoiceOrder(missionId: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ recording, parentId }: { recording: Blob; parentId?: string }) =>
      api.submitVoiceOrder(missionId, recording, parentId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.recommendations(missionId) }),
  });
}
