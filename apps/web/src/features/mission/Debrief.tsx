import { Link } from "react-router";
import { nm } from "../../components/format";
import type { Debrief as DebriefData } from "../../socle/ports";
import { ObjectiveList } from "./ObjectiveList";

export function Debrief({ debrief }: { debrief: DebriefData }) {
  const classifications = Object.entries(debrief.classification_by_contact);
  const cpas = Object.entries(debrief.closest_cpa_nm_by_contact);
  return (
    <section className="debrief" aria-labelledby="debrief-title">
      <h2 id="debrief-title">Débriefing</h2>
      <p className="score">
        Score <b>{debrief.score}</b> · objectifs atteints {debrief.objectives.filter((o) => o.achieved).length} /{" "}
        {debrief.objectives_total}
      </p>
      {debrief.closest_ships_distance_m !== null && debrief.closest_ships_distance_m !== undefined && (
        <p>Plus faible distance entre navires : {Math.round(debrief.closest_ships_distance_m)} m</p>
      )}
      <ObjectiveList objectives={debrief.objectives} />
      {(classifications.length > 0 || cpas.length > 0) && (
        <table className="card table">
          <caption className="lbl">Contacts</caption>
          <thead>
            <tr>
              <th scope="col">Contact</th>
              <th scope="col">CPA mini</th>
              <th scope="col">Classé</th>
              <th scope="col">Réel</th>
            </tr>
          </thead>
          <tbody>
            {[...new Set([...cpas.map(([id]) => id), ...classifications.map(([id]) => id)])].map((id) => {
              const c = debrief.classification_by_contact[id];
              const ok = c ? c.chosen === c.actual : undefined;
              return (
                <tr key={id}>
                  <th scope="row">{id}</th>
                  <td>{nm(debrief.closest_cpa_nm_by_contact[id], 2)}</td>
                  <td className={ok === false ? "bad" : undefined}>{c?.chosen ?? "—"}</td>
                  <td>{c?.actual ?? "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
      <Link className="btn green" to="/missions/nouvelle">
        Nouvelle mission
      </Link>
    </section>
  );
}
