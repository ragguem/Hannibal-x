import { Link } from "react-router";
import { ErrorPanel } from "../components/ErrorPanel";
import { Loading } from "../components/Loading";
import { useArchiveMission, useMissionHistory } from "../features/mission-setup/use-mission-setup";
import { describeError } from "../services/api-error";

const STATES: Record<string, string> = {
  planned: "Planifiée",
  ready: "Prête",
  launching: "Lancement…",
  running: "Lancée",
  archived: "Archivée",
};

/** Planned missions (`mission:plan`), most recent first, with the run phase read from `apps/api`. */
export function MissionHistoryPage() {
  const history = useMissionHistory();
  const archive = useArchiveMission();

  if (history.isPending) return <Loading label="Chargement des missions…" />;
  if (history.isError) return <ErrorPanel message={describeError(history.error).message} onRetry={() => void history.refetch()} />;

  const missions = history.data.pages.flatMap((p) => p.missions);
  return (
    <main className="page">
      <h1>Missions planifiées</h1>
      <p>
        <Link className="btn green" to="/missions/nouvelle">
          Planifier une mission
        </Link>
      </p>
      {archive.isError && (
        <p className="chip warn" role="alert">
          {describeError(archive.error).message}
        </p>
      )}
      {missions.length === 0 ? (
        <p className="card mut">Aucune mission planifiée.</p>
      ) : (
        <table className="table">
          <caption className="visually-hidden">Missions planifiées</caption>
          <thead>
            <tr>
              <th scope="col">Scénario</th>
              <th scope="col">Navire joué</th>
              <th scope="col">État</th>
              <th scope="col">Déroulé</th>
              <th scope="col">Créée le</th>
              <th scope="col">Actions</th>
            </tr>
          </thead>
          <tbody>
            {missions.map((m) => (
              <tr key={m.id}>
                <td>
                  {m.scenario_title} <span className="mono mut">v{m.scenario_version}</span>
                </td>
                <td className="mono">{m.player_ship}</td>
                <td>{STATES[m.state] ?? m.state}</td>
                <td className="mono">{m.run_phase ?? "—"}</td>
                <td className="mono">{new Date(m.created_at).toLocaleString("fr-FR")}</td>
                <td className="row">
                  {m.state === "running" && (
                    <Link className="btn sm" to={`/missions/${encodeURIComponent(m.id)}`}>
                      Ouvrir
                    </Link>
                  )}
                  {m.state !== "archived" && (
                    <button type="button" className="btn sm" disabled={archive.isPending} onClick={() => archive.mutate(m.id)}>
                      Archiver
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {history.hasNextPage && (
        <button type="button" className="btn" disabled={history.isFetchingNextPage} onClick={() => void history.fetchNextPage()}>
          Plus anciennes
        </button>
      )}
    </main>
  );
}
