import { useId, useMemo, useState } from "react";
import { useSearchParams } from "react-router";
import { ErrorPanel } from "../components/ErrorPanel";
import { Loading } from "../components/Loading";
import { AuditRegisterTable } from "../features/register/AuditRegisterTable";
import {
  OUTCOME_LABEL,
  filterTrails,
  groupByCommand,
  type TrailFilter,
  type TrailOutcome,
} from "../features/register/command-trail";
import { useAuditIntegrity, useAuditRegister, useRecordingUrl } from "../features/register/use-audit-register";
import { describeError } from "../services/api-error";

function IntegrityBadge() {
  const integrity = useAuditIntegrity();
  if (!integrity.data) return null;
  const { intact, checked_events, first_broken_seq } = integrity.data;
  return intact ? (
    <span className="chip">
      <span className="dot ok" /> Chaîne intacte · {checked_events} événements
    </span>
  ) : (
    <span className="chip warn" role="alert">
      Chaîne rompue à l'événement {first_broken_seq}
    </span>
  );
}

/** Replaces legacy `registre.html`: reads `ReadAudit` only, page by page. */
export function AuditRegisterPage() {
  const [params, setParams] = useSearchParams();
  const missionId = params.get("mission") ?? "";
  const [filter, setFilter] = useState<TrailFilter>({ source: "all", outcome: "all", search: "" });
  const register = useAuditRegister(missionId);
  const recordingUrl = useRecordingUrl();
  const ids = { mission: useId(), source: useId(), outcome: useId(), search: useId() };

  const trails = useMemo(
    () => groupByCommand(register.data?.pages.flatMap((page) => page.events) ?? []),
    [register.data],
  );
  const shown = useMemo(() => filterTrails(trails, filter), [trails, filter]);

  return (
    <main className="page register-page">
      <div className="row wrap">
        <h1 className="grow">Registre</h1>
        <IntegrityBadge />
      </div>
      <p className="mut">
        Chaque commande garde son audio, sa transcription, le signal retenu et la décision. Le registre n'est jamais
        réécrit : on y ajoute seulement.
      </p>
      <form className="card row wrap filters" role="search" onSubmit={(e) => e.preventDefault()}>
        <label htmlFor={ids.mission} className="lbl">
          Mission
        </label>
        <input
          id={ids.mission}
          className="mono"
          placeholder="toutes"
          defaultValue={missionId}
          onBlur={(e) => {
            const value = e.target.value.trim();
            setParams(value ? { mission: value } : {});
          }}
        />
        <label htmlFor={ids.source} className="lbl">
          Source
        </label>
        <select
          id={ids.source}
          value={filter.source}
          onChange={(e) => setFilter({ ...filter, source: e.target.value as TrailFilter["source"] })}
        >
          <option value="all">toutes</option>
          <option value="voice">voix</option>
          <option value="keyboard">clavier</option>
        </select>
        <label htmlFor={ids.outcome} className="lbl">
          Décision
        </label>
        <select
          id={ids.outcome}
          value={filter.outcome}
          onChange={(e) => setFilter({ ...filter, outcome: e.target.value as TrailFilter["outcome"] })}
        >
          <option value="all">toutes</option>
          {(Object.keys(OUTCOME_LABEL) as TrailOutcome[]).map((o) => (
            <option key={o} value={o}>
              {OUTCOME_LABEL[o]}
            </option>
          ))}
        </select>
        <label htmlFor={ids.search} className="lbl">
          Texte
        </label>
        <input
          id={ids.search}
          type="search"
          value={filter.search}
          onChange={(e) => setFilter({ ...filter, search: e.target.value })}
        />
      </form>
      {register.isPending && <Loading label="Lecture du registre…" />}
      {register.isError && (
        <ErrorPanel message={describeError(register.error).message} onRetry={() => void register.refetch()} />
      )}
      {register.data && (
        <section className="card">
          <AuditRegisterTable trails={shown} recordingUrl={recordingUrl} />
          <div className="row">
            <small className="mut grow">
              {shown.length} ligne(s) sur {trails.length}
            </small>
            {register.hasNextPage && (
              <button
                type="button"
                className="btn sm"
                disabled={register.isFetchingNextPage}
                onClick={() => void register.fetchNextPage()}
              >
                Charger la suite
              </button>
            )}
            <button type="button" className="btn ghost sm" onClick={() => void register.refetch()}>
              Actualiser
            </button>
          </div>
        </section>
      )}
    </main>
  );
}
