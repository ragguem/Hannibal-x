interface ShipPickerProps {
  ships: string[];
  guide: string;
  selected: string | undefined;
  onSelect: (ship: string) => void;
}

export function ShipPicker({ ships, guide, selected, onSelect }: ShipPickerProps) {
  return (
    <fieldset className="card">
      <legend className="lbl">Votre navire</legend>
      <div className="row wrap">
        {ships.map((ship) => (
          <label key={ship} className={ship === selected ? "pick on" : "pick"}>
            <input type="radio" name="ship" value={ship} checked={ship === selected} onChange={() => onSelect(ship)} />
            {ship.toUpperCase()}
            {ship === guide && <span className="badge guide">guide</span>}
          </label>
        ))}
      </div>
    </fieldset>
  );
}
