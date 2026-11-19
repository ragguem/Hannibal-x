import { formatClock } from "./format-time";
import { EVENT_LABEL, OUTCOME_LABEL, type CommandTrail } from "./command-trail";

const shortId = (id: string) => id.slice(0, 8);

interface AuditRegisterTableProps {
  trails: CommandTrail[];
  recordingUrl: (commandId: string) => string;
}

/** Each command keeps its recording, what was heard or typed, the signal, the decision and its history. */
export function AuditRegisterTable({ trails, recordingUrl }: AuditRegisterTableProps) {
  if (trails.length === 0) return <p className="mut">Aucun événement pour ces critères.</p>;
  return (
    <table className="table register">
      <caption className="visually-hidden">Registre des commandes</caption>
      <thead>
        <tr>
          <th scope="col">Commande</th>
          <th scope="col">Opérateur</th>
          <th scope="col">Audio</th>
          <th scope="col">Entendu ou saisi</th>
          <th scope="col">Signal</th>
          <th scope="col">Décision</th>
          <th scope="col">Historique</th>
        </tr>
      </thead>
      <tbody>
        {trails.map((t) => (
          <tr key={t.key} className={t.outcome}>
            <td className="mono">
              {t.commandId ? shortId(t.commandId) : EVENT_LABEL[t.events[0]?.event ?? ""] ?? t.events[0]?.event}
              {t.parentId && <small className="mut block">corrige {shortId(t.parentId)}</small>}
              {t.doctrineStatus && <small className="mut block">doctrine : {t.doctrineStatus}</small>}
            </td>
            <td>{t.actor ?? "système"}</td>
            <td>
              {t.hasRecording && t.commandId ? (
                <audio controls preload="none" src={recordingUrl(t.commandId)} aria-label={`Audio de la commande ${shortId(t.commandId)}`}>
                  {/* The transcript in the next column is the caption. */}
                  <track kind="captions" />
                </audio>
              ) : (
                <small className="mut">{t.source === "keyboard" ? "saisie au clavier" : "—"}</small>
              )}
            </td>
            <td className="mono" lang="en">
              {t.heard ?? (t.source === "keyboard" ? t.textEn : null) ?? "—"}
            </td>
            <td>
              {t.textEn && <span className="mono">{t.textEn}</span>}
              {t.textFr && <small className="fr block">{t.textFr}</small>}
              {t.refusalReason && <small className="bad block">{t.refusalReason}</small>}
            </td>
            <td>
              <span className={`badge outcome ${t.outcome}`}>{OUTCOME_LABEL[t.outcome]}</span>
            </td>
            <td>
              <ol className="history">
                {t.events.map((e) => (
                  <li key={e.seq}>
                    <span className="mono">{formatClock(e.at)}</span> {EVENT_LABEL[e.event] ?? e.event}
                    {e.actor && e.actor !== t.actor ? ` · ${e.actor}` : ""}
                  </li>
                ))}
              </ol>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
