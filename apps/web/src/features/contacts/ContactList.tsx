import { memo } from "react";
import { deg3, nm } from "../../components/format";
import type { Classification, Contact } from "../../socle/ports";

const CLASSIFICATIONS: Classification[] = ["inconnu", "ami", "neutre", "hostile"];

interface ContactListProps {
  contacts: Contact[];
  onClassify: (contactId: string, classification: Classification) => void;
  disabled: boolean;
}

export const ContactList = memo(function ContactList({ contacts, onClassify, disabled }: ContactListProps) {
  return (
    <section className="card" aria-labelledby="contacts-title">
      <h2 id="contacts-title" className="lbl">
        Contacts
      </h2>
      {contacts.length === 0 && <p className="mut">Aucun contact.</p>}
      <ul className="contacts">
        {contacts.map((c) => (
          <li key={c.id} className={`contact-card ${c.classification}`}>
            <div className="row">
              <b>{c.id}</b>
              <span className="mut">{c.category}</span>
              <span className="grow" />
              <label className="visually-hidden" htmlFor={`cls-${c.id}`}>
                Classification de {c.id}
              </label>
              <select
                id={`cls-${c.id}`}
                value={c.classification}
                disabled={disabled}
                onChange={(e) => onClassify(c.id, e.target.value as Classification)}
              >
                {CLASSIFICATIONS.map((k) => (
                  <option key={k} value={k}>
                    {k}
                  </option>
                ))}
              </select>
            </div>
            <small className="mono">
              {c.bearing_deg !== null && c.bearing_deg !== undefined ? `${deg3(c.bearing_deg)}° · ` : ""}
              {nm(c.range_nm)} · cap {deg3(c.course_deg)}° {Math.round(c.speed_kn)} kn · CPA {nm(c.cpa_nm, 2)}
              {c.tcpa_min !== null && c.tcpa_min !== undefined ? ` dans ${Math.round(c.tcpa_min)} min` : ""}
            </small>
          </li>
        ))}
      </ul>
    </section>
  );
});
