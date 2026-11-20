import { useEffect, useId, useRef, useState } from "react";
import { Icon } from "../components/Icon";

interface UserMenuProps {
  username: string;
  role: string;
  signingOut: boolean;
  onSignOut: () => void;
}

/** Disclosure button (APG): the panel is a plain list of actions, reached with Tab. */
export function UserMenu({ username, role, signingOut, onSignOut }: UserMenuProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelId = useId();

  useEffect(() => {
    if (!open) return;
    const closeOnOutsideClick = (event: PointerEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setOpen(false);
      triggerRef.current?.focus();
    };
    document.addEventListener("pointerdown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  return (
    <div className="user-menu" ref={containerRef}>
      <button
        ref={triggerRef}
        type="button"
        className="user-menu-trigger"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
      >
        <span className="user-avatar" aria-hidden="true">
          <Icon name="user" size={20} />
        </span>
        <span className="user-identity">
          <b>{username}</b>
          <small>{role}</small>
        </span>
        <span className={open ? "user-chevron open" : "user-chevron"} aria-hidden="true">
          <Icon name="chevron" size={16} />
        </span>
      </button>
      <div className="user-menu-list" id={panelId} hidden={!open}>
        <button type="button" className="user-menu-item" disabled={signingOut} onClick={onSignOut}>
          <Icon name="logout" size={16} /> Se déconnecter
        </button>
      </div>
    </div>
  );
}
