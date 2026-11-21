import { useId, useState, type ChangeEvent } from "react";
import { ErrorPanel } from "../components/ErrorPanel";
import { Loading } from "../components/Loading";
import { useCatalogScenarios, useScenarioAction } from "../features/scenario-catalog/use-scenario-catalog";
import { describeError } from "../services/api-error";
import { useApi } from "../socle/composition";
import type { ScenarioEntry } from "../socle/ports";

function download(fileName: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: "application/yaml" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  link.click();
  URL.revokeObjectURL(url);
}

/** Scenario catalog (`catalog:manage`): each import is a new immutable version; only the published one is played. */
export function ScenarioCatalogPage() {
  const api = useApi();
  const scenarios = useCatalogScenarios();
  const action = useScenarioAction();
  const fileId = useId();
  const [exportError, setExportError] = useState<string | null>(null);

  const importFile = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => action.mutate({ kind: "import", yaml: typeof reader.result === "string" ? reader.result : "" });
    reader.readAsText(file);
  };

  const exportVersion = async (entry: ScenarioEntry) => {
    setExportError(null);
    try {
      download(`${entry.id}.v${entry.latest_version}.yaml`, await api.exportScenario(entry.id, entry.latest_version));
    } catch (e) {
      setExportError(describeError(e).message);
    }
  };

  if (scenarios.isPending) return <Loading label="Chargement des scénarios…" />;
  if (scenarios.isError) return <ErrorPanel message={describeError(scenarios.error).message} onRetry={() => void scenarios.refetch()} />;

  const busy = action.isPending;
  return (
    <main className="page">
      <h1>Scénarios</h1>
      <p className="mut">Chaque import crée une version ; seule la version publiée est jouée. Un scénario archivé est conservé.</p>
      {(action.isError || exportError) && (
        <p className="chip warn" role="alert">
          {action.isError ? describeError(action.error).message : exportError}
        </p>
      )}
      <div className="card row wrap">
        <label htmlFor={fileId} className="lbl">
          Importer un fichier YAML
        </label>
        <input id={fileId} type="file" accept=".yaml,.yml" disabled={busy} onChange={importFile} />
      </div>
      <table className="table">
        <caption className="visually-hidden">Scénarios</caption>
        <thead>
          <tr>
            <th scope="col">Identifiant</th>
            <th scope="col">Titre</th>
            <th scope="col">Niveau</th>
            <th scope="col">Publiée</th>
            <th scope="col">Dernière</th>
            <th scope="col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {scenarios.data.map((s) => (
            <tr key={s.id}>
              <td className="mono">{s.id}</td>
              <td>{s.title}</td>
              <td>{s.level}</td>
              <td className="mono">{s.published_version ? `v${s.published_version}` : "—"}</td>
              <td className="mono">v{s.latest_version}</td>
              <td className="row">
                {s.archived_at ? (
                  <span className="chip warn">Archivé</span>
                ) : (
                  <>
                    {s.published_version !== s.latest_version && (
                      <button
                        type="button"
                        className="btn sm green"
                        disabled={busy}
                        onClick={() => action.mutate({ kind: "publish", id: s.id, version: s.latest_version })}
                      >
                        Publier v{s.latest_version}
                      </button>
                    )}
                    <button type="button" className="btn sm" disabled={busy} onClick={() => action.mutate({ kind: "archive", id: s.id })}>
                      Archiver
                    </button>
                  </>
                )}
                <button type="button" className="btn sm" onClick={() => void exportVersion(s)}>
                  Exporter v{s.latest_version}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
