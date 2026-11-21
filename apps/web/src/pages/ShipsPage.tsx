import { useId, useState, type SyntheticEvent } from "react";
import { ErrorPanel } from "../components/ErrorPanel";
import { Loading } from "../components/Loading";
import { useShipAction, useShipClasses, useShips, type ShipAction } from "../features/ships/use-ships";
import { describeError } from "../services/api-error";
import type { CatalogShip, ShipClass } from "../socle/ports";

const EMPTY_CLASS = { code: "", label: "", min: "3", max: "28", radius: "", length: "" };

function NewClassForm({ onCreate, busy }: { onCreate: (body: ShipClass) => void; busy: boolean }) {
  const ids = { code: useId(), label: useId(), min: useId(), max: useId(), radius: useId(), length: useId() };
  const [form, setForm] = useState(EMPTY_CLASS);
  const field = (key: keyof typeof EMPTY_CLASS) => ({
    id: ids[key],
    value: form[key],
    onChange: (e: { target: { value: string } }) => setForm({ ...form, [key]: e.target.value }),
    required: true,
  });
  const submit = (event: SyntheticEvent<HTMLFormElement>) => {
    event.preventDefault();
    onCreate({
      code: form.code.trim(),
      label: form.label.trim(),
      min_speed_knots: Number(form.min),
      max_speed_knots: Number(form.max),
      turn_radius_meters: Number(form.radius),
      length_meters: Number(form.length),
    });
    setForm(EMPTY_CLASS);
  };
  return (
    <form className="card row wrap" aria-label="Nouvelle classe" onSubmit={submit}>
      <label htmlFor={ids.code} className="lbl">
        Code
      </label>
      <input className="mono" pattern="[a-z][a-z0-9_\-]{1,31}" {...field("code")} />
      <label htmlFor={ids.label} className="lbl">
        Libellé
      </label>
      <input maxLength={64} {...field("label")} />
      <label htmlFor={ids.min} className="lbl">
        Vitesse min (nds)
      </label>
      <input type="number" min={1} max={60} {...field("min")} />
      <label htmlFor={ids.max} className="lbl">
        Vitesse max (nds)
      </label>
      <input type="number" min={1} max={60} {...field("max")} />
      <label htmlFor={ids.radius} className="lbl">
        Rayon de giration (m)
      </label>
      <input type="number" min={1} max={5000} {...field("radius")} />
      <label htmlFor={ids.length} className="lbl">
        Longueur (m)
      </label>
      <input type="number" min={1} max={500} {...field("length")} />
      <button type="submit" className="btn green" disabled={busy}>
        Créer la classe
      </button>
    </form>
  );
}

function NewShipForm({ classes, onCreate, busy }: { classes: ShipClass[]; onCreate: (callSign: string, classCode: string) => void; busy: boolean }) {
  const ids = { callSign: useId(), classCode: useId() };
  const [callSign, setCallSign] = useState("");
  const [classCode, setClassCode] = useState(classes[0]?.code ?? "");
  const submit = (event: SyntheticEvent<HTMLFormElement>) => {
    event.preventDefault();
    onCreate(callSign.trim(), classCode);
    setCallSign("");
  };
  return (
    <form className="card row wrap" aria-label="Nouveau navire" onSubmit={submit}>
      <label htmlFor={ids.callSign} className="lbl">
        Nom d'appel
      </label>
      <input
        id={ids.callSign}
        className="mono"
        value={callSign}
        onChange={(e) => setCallSign(e.target.value)}
        pattern="[a-z][a-z0-9\-]{1,23}"
        title="2 à 24 caractères : minuscules, chiffres ou tiret, en commençant par une lettre"
        required
      />
      <label htmlFor={ids.classCode} className="lbl">
        Classe
      </label>
      <select id={ids.classCode} value={classCode} onChange={(e) => setClassCode(e.target.value)}>
        {classes.map((c) => (
          <option key={c.code} value={c.code}>
            {c.label}
          </option>
        ))}
      </select>
      <button type="submit" className="btn green" disabled={busy}>
        Ajouter le navire
      </button>
    </form>
  );
}

function ShipRow({ ship, classes, busy, onAction }: { ship: CatalogShip; classes: ShipClass[]; busy: boolean; onAction: (a: ShipAction) => void }) {
  return (
    <tr>
      <td className="mono">{ship.call_sign}</td>
      <td>
        <select
          aria-label={`Classe de ${ship.call_sign}`}
          value={ship.class_code}
          disabled={busy}
          onChange={(e) => onAction({ kind: "class", shipId: ship.id, classCode: e.target.value })}
        >
          {classes.map((c) => (
            <option key={c.code} value={c.code}>
              {c.label}
            </option>
          ))}
        </select>
      </td>
      <td>{ship.active ? <span className="chip">En service</span> : <span className="chip warn">Retiré</span>}</td>
      <td>
        {ship.active ? (
          <button type="button" className="btn sm" disabled={busy} onClick={() => onAction({ kind: "retire", shipId: ship.id })}>
            Retirer
          </button>
        ) : (
          <button type="button" className="btn sm" disabled={busy} onClick={() => onAction({ kind: "reactivate", shipId: ship.id })}>
            Remettre en service
          </button>
        )}
      </td>
    </tr>
  );
}

/** Ship catalog (`catalog:manage`). Speed bounds of a class become the limits of the missions played on its ships. */
export function ShipsPage() {
  const classes = useShipClasses();
  const ships = useShips();
  const action = useShipAction();

  if (classes.isPending || ships.isPending) return <Loading label="Chargement du catalogue…" />;
  if (classes.isError || ships.isError) {
    return <ErrorPanel message={describeError(classes.error ?? ships.error).message} onRetry={() => void ships.refetch()} />;
  }

  return (
    <main className="page">
      <h1>Navires</h1>
      <p className="mut">Un navire retiré n'est plus proposé à la planification. Rien n'est supprimé.</p>
      {action.isError && (
        <p className="chip warn" role="alert">
          {describeError(action.error).message}
        </p>
      )}
      <h2>Classes</h2>
      <table className="table">
        <caption className="visually-hidden">Classes</caption>
        <thead>
          <tr>
            <th scope="col">Code</th>
            <th scope="col">Libellé</th>
            <th scope="col">Vitesses (nds)</th>
            <th scope="col">Rayon de giration (m)</th>
            <th scope="col">Longueur (m)</th>
          </tr>
        </thead>
        <tbody>
          {classes.data.map((c) => (
            <tr key={c.code}>
              <td className="mono">{c.code}</td>
              <td>{c.label}</td>
              <td className="mono">
                {c.min_speed_knots} – {c.max_speed_knots}
              </td>
              <td className="mono">{c.turn_radius_meters}</td>
              <td className="mono">{c.length_meters}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <NewClassForm busy={action.isPending} onCreate={(body) => action.mutate({ kind: "create-class", body })} />
      <h2>Flotte</h2>
      <NewShipForm
        classes={classes.data}
        busy={action.isPending}
        onCreate={(call_sign, class_code) => action.mutate({ kind: "create", body: { call_sign, class_code } })}
      />
      <table className="table">
        <caption className="visually-hidden">Flotte</caption>
        <thead>
          <tr>
            <th scope="col">Nom d'appel</th>
            <th scope="col">Classe</th>
            <th scope="col">État</th>
            <th scope="col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {ships.data.map((ship) => (
            <ShipRow key={ship.id} ship={ship} classes={classes.data} busy={action.isPending} onAction={(a) => action.mutate(a)} />
          ))}
        </tbody>
      </table>
    </main>
  );
}
