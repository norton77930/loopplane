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
import { useTranslation } from "../i18n/i18n";
import { inspectionStatusLabel } from "../inspection-status";
import {
  paneReadOnlyReason,
  paneStateLabel,
  permissionPostureLabel,
} from "../vocabulary";

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
  /** Whether a different pane holds the single interactive lease. */
  otherPaneHoldsLease?: boolean;
  /** Claim the interactive lease for this pane; omit to show no action. */
  onRequestInteractive?: () => void;
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
  otherPaneHoldsLease = false,
  onRequestInteractive,
  unavailable = false,
  onClose,
  returnFocus,
}: InspectionSidebarProps) {
  const { t } = useTranslation();
  const readOnlyReason = paneReadOnlyReason(leaseOwner, otherPaneHoldsLease);
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
      <h2>{t("inspection.heading")}</h2>
      {unavailable ? (
        <p role="status">{t("inspection.unavailable")}</p>
      ) : (
        <dl>
          <div>
            <dt>{t("inspection.session")}</dt>
            <dd>{title || sessionId || "—"}</dd>
          </div>
          {/* One fact, not two rows of implementation naming. The raw values
              stay reachable on hover for anyone who wants them. A host that
              does not run panes at all (Web) passes neither and gets no row,
              rather than a row reading "Unknown". */}
          {(mode !== undefined || leaseOwner !== undefined) && (
          <div>
            <dt>{t("pane.thisPane")}</dt>
            <dd title={`mode=${mode ?? "unknown"} lease_owner=${Boolean(leaseOwner)}`}>
              {t(paneStateLabel(mode, leaseOwner))}
              {readOnlyReason && (
                <span className="pane-state-reason"> {t(readOnlyReason)}</span>
              )}
              {onRequestInteractive && !leaseOwner && (
                <button
                  type="button"
                  className="pane-state-action"
                  onClick={onRequestInteractive}
                >
                  {t("pane.takeOver")}
                </button>
              )}
            </dd>
          </div>
          )}
          {inspection ? <>
            <div><dt>{t("inspection.cost")}</dt><dd>{inspectionStatusLabel(inspection.cost?.status)}</dd></div>
            <div><dt>{t("inspection.context")}</dt><dd>{inspectionStatusLabel(inspection.context?.status)}</dd></div>
            <div><dt>{t("inspection.uploads")}</dt><dd>{inspectionStatusLabel(inspection.uploads?.status)}</dd></div>
            <div><dt>{t("inspection.artifacts")}</dt><dd>{inspectionStatusLabel(inspection.artifacts?.status)}</dd></div>
          </> : null}
          {agentControls ? <>
            <div>
              <dt>{t("inspection.posture")}</dt>
              {/* Not the raw mode id: "acceptEdits" says nothing about what the
                  agent will do next. The id stays available on hover. */}
              <dd
                title={
                  agentControls.activeRun?.mode ??
                  agentControls.lastAcceptedRun?.mode ??
                  agentControls.defaultMode ??
                  "default"
                }
              >
                {agentControls.unavailable
                  ? t("value.unavailable")
                  : (() => {
                      const key = permissionPostureLabel(agentControls);
                      return key ? t(key) : t("value.unknown");
                    })()}
              </dd>
            </div>
            <div><dt>{t("inspection.pricing")}</dt><dd>{agentControls.budget.pricing === "unpriced" ? t("value.unpriced") : inspectionStatusLabel(agentControls.budget.pricing)}</dd></div>
          </> : null}
          {capabilities === null ? <div><dt>{t("inspection.capabilities")}</dt><dd>{t("value.unavailable")}</dd></div> : capabilities.map((capability) => (
            <div key={capability.id}><dt>{capability.label}</dt><dd>{capability.available ? capability.status === "private_config" ? t("value.unavailable") : inspectionStatusLabel(capability.status) : t("value.unavailable")}</dd></div>
          ))}
          {lines.map((line) => (
            <div key={line}>
              <dt>{t("inspection.detail")}</dt>
              <dd>{line}</dd>
            </div>
          ))}
        </dl>
      )}
    </aside>
  );
}
