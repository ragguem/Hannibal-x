import { useState, type ReactNode } from "react";
import { Link } from "react-router";
import { Icon, type IconName } from "./Icon";

interface PanelProps {
  id: string;
  title: string;
  icon: IconName;
  /** "Voir tout" link; omitted while the full screen does not exist. */
  seeAllTo?: string;
  actions?: ReactNode;
  /** Adds a header button that folds the body away. */
  collapsible?: boolean;
  className?: string;
  children: ReactNode;
}

/** Titled card shared by the dashboard and the mission planner. */
export function Panel({ id, title, icon, seeAllTo, actions, collapsible = false, className, children }: PanelProps) {
  const [open, setOpen] = useState(true);
  const bodyId = `${id}-body`;
  return (
    <section className={`card section-panel ${className ?? ""}`} aria-labelledby={id}>
      <header className="section-panel-head">
        <Icon name={icon} />
        <h2 id={id} tabIndex={-1}>
          {title}
        </h2>
        <span className="grow" />
        {actions}
        {seeAllTo && (
          <Link to={seeAllTo} className="see-all">
            Voir tout <Icon name="arrow" size={14} />
          </Link>
        )}
        {collapsible && (
          <button
            type="button"
            className="icon-btn btn sm ghost panel-toggle"
            aria-expanded={open}
            aria-controls={bodyId}
            aria-label={open ? `Replier ${title}` : `Déplier ${title}`}
            onClick={() => setOpen((value) => !value)}
          >
            <Icon name="chevron" size={16} />
          </button>
        )}
      </header>
      {collapsible ? (
        <div id={bodyId} className="section-panel-body" hidden={!open}>
          {children}
        </div>
      ) : (
        children
      )}
    </section>
  );
}
