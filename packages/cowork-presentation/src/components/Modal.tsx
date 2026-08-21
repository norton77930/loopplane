import { type ReactNode } from "react";

import { useFocusTrap } from "../hooks/useFocusTrap";

// A true modal (unit 032, FR-001): a dimming backdrop + a focus-trapped panel with
// role="dialog" + aria-modal. Esc and a backdrop click call onClose; focus is restored to the
// opener when it unmounts (via useFocusTrap).
// Moved from apps/web in 083 Wave 3; apps/web re-exports it unchanged.
export function Modal({
  onClose,
  label,
  children,
}: {
  onClose: () => void;
  label: string;
  children: ReactNode;
}) {
  const ref = useFocusTrap<HTMLDivElement>(onClose);
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={label}
        ref={ref}
        onClick={(event) => event.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}
