/**
 * Public-safe right inspection sidebar (078 T054).
 *
 * Displays only caller-supplied safe projections — never raw paths, secrets,
 * or private configuration.
 */

import type {
  PresentationAgentControls,
  PresentationCapability,
  PresentationInspection,
} from "../models";
import { dismissOnEscape } from "../focus";
import { inspectionStatusLabel } from "../inspection-status";

export type InspectionSidebarProps = {
  sessionId?: string | null;
  title?: string | null;
  mode?: "interactive" | "read_only" | string;
  leaseOwner?: boolean;
  /** Bounded public-safe lines (cost, controls, etc.). */
  lines?: string[];
  /** Host-owned projection. The component never reads capabilities directly. */
  inspection?: PresentationInspection | null;
  /** Host-owned accepted/active control posture, never a renderer draft. */
  agentControls?: PresentationAgentControls | null;
  /** Host-owned capabilities only; unavailable entries never become actions here. */
  capabilities?: PresentationCapability[] | null;
  unavailable?: boolean;
  /** Optional controlled close action for keyboard-accessible overlays. */
  onClose?: () => void;
  /** Stable opener to restore after an Escape close. */
  returnFocus?: HTMLElement | null;
};

export function InspectionSidebar({
  sessionId,
  title,
  mode,
  leaseOwner,
  lines = [],
  inspection = null,
  agentControls = null,
  capabilities = null,
  unavailable = false,
  onClose,
  returnFocus,
}: InspectionSidebarProps) {
  return (
    <aside
      className="inspection-sidebar"
      aria-label="Inspection"
      data-testid="inspection-sidebar"
      tabIndex={onClose ? -1 : undefined}
      onKeyDown={(event) => {
        if (onClose) dismissOnEscape(event, onClose, returnFocus, null);
      }}
    >
      <h2>Inspection</h2>
      {unavailable ? (
        <p role="status">Inspection unavailable.</p>
      ) : (
        <dl>
          <div>
            <dt>Session</dt>
            <dd>{title || sessionId || "—"}</dd>
          </div>
          <div>
            <dt>Mode</dt>
            <dd>{mode || "—"}</dd>
          </div>
          <div>
            <dt>Lease</dt>
            <dd>{leaseOwner ? "owner" : "not owner"}</dd>
          </div>
          {inspection ? <>
            <div><dt>Cost</dt><dd>{inspectionStatusLabel(inspection.cost?.status)}</dd></div>
            <div><dt>Context</dt><dd>{inspectionStatusLabel(inspection.context?.status)}</dd></div>
            <div><dt>Uploads</dt><dd>{inspectionStatusLabel(inspection.uploads?.status)}</dd></div>
            <div><dt>Artifacts</dt><dd>{inspectionStatusLabel(inspection.artifacts?.status)}</dd></div>
          </> : null}
          {agentControls ? <>
            <div><dt>Control posture</dt><dd>{agentControls.unavailable ? "Unavailable" : agentControls.activeRun?.mode ?? agentControls.lastAcceptedRun?.mode ?? "Unknown"}</dd></div>
            <div><dt>Pricing</dt><dd>{agentControls.budget.pricing === "unpriced" ? "Unpriced" : inspectionStatusLabel(agentControls.budget.pricing)}</dd></div>
          </> : null}
          {capabilities === null ? <div><dt>Capabilities</dt><dd>Unavailable</dd></div> : capabilities.map((capability) => (
            <div key={capability.id}><dt>{capability.label}</dt><dd>{capability.available ? capability.status === "private_config" ? "Unavailable" : inspectionStatusLabel(capability.status) : "Unavailable"}</dd></div>
          ))}
          {lines.map((line) => (
            <div key={line}>
              <dt>Detail</dt>
              <dd>{line}</dd>
            </div>
          ))}
        </dl>
      )}
    </aside>
  );
}
