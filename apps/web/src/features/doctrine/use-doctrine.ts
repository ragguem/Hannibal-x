import { useMutation, useQuery } from "@tanstack/react-query";
import { useApi } from "../../socle/composition";
import type { DoctrineQuestion } from "../../socle/ports";
import { queryKeys } from "../../socle/query-keys";

/** Answers can take ~10 s on the shared GPU and are never retried: a 429 tells the user to try again. */
export function useAskDoctrine() {
  const api = useApi();
  return useMutation({ mutationFn: (body: DoctrineQuestion) => api.askDoctrine(body) });
}

export function usePublications() {
  const api = useApi();
  return useQuery({ queryKey: queryKeys.publications, queryFn: () => api.listPublications(), staleTime: 300_000 });
}

export const GLOSSARY_MIN_CHARS = 2;

export function useGlossary(query: string) {
  const api = useApi();
  const q = query.trim();
  return useQuery({
    queryKey: queryKeys.glossary(q.toLowerCase()),
    queryFn: () => api.searchGlossary(q),
    enabled: q.length >= GLOSSARY_MIN_CHARS,
    staleTime: 300_000,
  });
}

export function useExplainCommand(commandId: string) {
  const api = useApi();
  return useMutation({ mutationKey: queryKeys.explanation(commandId), mutationFn: () => api.explainCommand(commandId) });
}

/** Swaps the unknown term for the chosen proposal, whole word only, keeping the rest of the question. */
export function replaceTerm(question: string, unknown: string, proposal: string): string {
  const escaped = unknown.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return question.replace(new RegExp(`\\b${escaped}\\b`, "gi"), proposal);
}
