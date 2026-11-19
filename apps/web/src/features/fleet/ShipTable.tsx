import { memo } from "react";
import { deg3, knots } from "../../components/format";
import type { Ship } from "../../socle/ports";

export const ShipTable = memo(function ShipTable({ ships, player }: { ships: Ship[]; player: string }) {
  return (
    <table className="card table">
      <caption className="lbl">Navires</caption>
      <thead>
        <tr>
          <th scope="col">Navire</th>
          <th scope="col">Rôle</th>
          <th scope="col">Cap</th>
          <th scope="col">Vitesse</th>
          <th scope="col">État</th>
        </tr>
      </thead>
      <tbody>
        {ships.map((s) => (
          <tr key={s.name} className={s.name === player ? "me" : undefined}>
            <th scope="row">{s.name.toUpperCase()}</th>
            <td>{s.role}</td>
            <td className="mono">{deg3(s.heading_deg)}°</td>
            <td className="mono">{knots(s.speed_mps)} kn</td>
            <td>{s.status_for_player}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
});
