import { useQuery } from "@tanstack/react-query";
import { useApi } from "../../socle/composition";
import { queryKeys } from "../../socle/query-keys";

function useRecommendations(missionId: string, running: boolean) {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.recommendations(missionId),
    queryFn: () => api.listRecommendations(missionId),
    enabled: running,
    refetchInterval: running ? 5000 : false,
    staleTime: 0,
  });
}

interface RecommendationListProps {
  missionId: string;
  running: boolean;
  onUse: (text: string) => void;
}

export function RecommendationList({ missionId, running, onUse }: RecommendationListProps) {
  const { data = [] } = useRecommendations(missionId, running);
  if (data.length === 0) return null;
  return (
    <section className="card teal" aria-labelledby="reco-title">
      <h2 id="reco-title" className="lbl teal">
        Recommandations
      </h2>
      <ul className="recommendations">
        {data.map((r) => (
          <li key={`${r.kind}-${r.text}`}>
            <span className="mono">{r.text}</span>
            <small className="mut">{r.reason}</small>
            <button type="button" className="btn sm" onClick={() => onUse(r.text)}>
              Reprendre
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
