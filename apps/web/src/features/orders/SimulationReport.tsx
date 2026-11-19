import { clock } from "../../components/format";
import type { Simulation } from "../../socle/ports";

export function SimulationReport({ simulation, onClose }: { simulation: Simulation; onClose: () => void }) {
  const risks = (simulation.contact_cpas ?? []).filter((c) => c.at_risk).length + (simulation.ships_passings ?? []).filter((p) => p.at_risk).length;
  return (
    <section className="card teal" aria-labelledby="sim-title">
      <div className="row">
        <h2 id="sim-title" className="lbl teal grow">
          Simulation
        </h2>
        <button type="button" className="btn ghost sm" onClick={onClose}>
          Effacer
        </button>
      </div>
      {!simulation.accepted ? (
        <div role="alert">
          <b>Signal refusé :</b> {simulation.refusal_reason}
          {simulation.hint && <p className="mut">{simulation.hint}</p>}
        </div>
      ) : (
        <>
          {simulation.text_fr && <p className="fr">{simulation.text_fr}</p>}
          <p>
            Destinataires : {(simulation.recipients ?? []).join(", ") || "—"} ·{" "}
            <b className={risks > 0 ? "bad" : "good"}>{risks > 0 ? `${risks} risque(s)` : "aucun risque détecté"}</b>
          </p>
          <ul className="sim-list">
            {(simulation.contact_cpas ?? []).map((c) => (
              <li key={`${c.ship}-${c.contact_id}`} className={c.at_risk ? "bad" : undefined}>
                {c.ship.toUpperCase()} / {c.contact_id} : CPA {c.cpa_nm.toFixed(2)} NM (sans l'ordre {c.cpa_nm_without_order.toFixed(2)}) dans{" "}
                {clock(c.tcpa_s)}
              </li>
            ))}
            {(simulation.ships_passings ?? []).map((p) => (
              <li key={`${p.ship_a}-${p.ship_b}-${p.at_s}`} className={p.at_risk ? "bad" : undefined}>
                {p.ship_a.toUpperCase()} / {p.ship_b.toUpperCase()} : {Math.round(p.distance_m)} m à {clock(p.at_s)}
              </li>
            ))}
          </ul>
          <p className="mut">Trajectoires prévues en pointillés sur le radar.</p>
        </>
      )}
    </section>
  );
}
