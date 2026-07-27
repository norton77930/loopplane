import { useEffect, useState } from "react";

import type { ApiClient } from "../../api/client";
import type {
  AgentControlProjection,
  MonthlyCostView,
  SessionCostView,
  WorkspaceContext,
} from "../../api/types";
import { useTranslation } from "../../i18n/i18n";

export interface SessionContextSummary {
  context_id?: string | null;
  context_name?: string | null;
  context_workspace_label?: string | null;
  context_status?: string | null;
}

interface Props {
  client?: ApiClient;
  sessionId?: string | null;
  sessionOwned?: boolean;
  sessionContext?: SessionContextSummary | null;
  onContextBound?: () => void | Promise<void>;
  projection: AgentControlProjection | null;
  loading: boolean;
  failed: boolean;
  permissionModeDraft: string | null;
  onPermissionModeChange: (mode: string | null) => void;
  onRefresh: () => void;
  sessionCost?: SessionCostView | null;
  monthlyCost?: MonthlyCostView | null;
  costLoading?: boolean;
  costFailed?: boolean;
  sessionCostLoading?: boolean;
  monthlyCostLoading?: boolean;
  sessionCostFailed?: boolean;
  monthlyCostFailed?: boolean;
}

function postureMode(
  posture: AgentControlProjection["permission"]["active_run"],
  unavailable: string,
) {
  return posture?.mode ?? unavailable;
}

function costText(
  value: string | null | undefined,
  pricing: AgentControlProjection["budget"]["pricing"],
  loading: boolean,
  failed: boolean,
  label: (key: string) => string,
) {
  if (loading) return label("agentControls.cost.loading");
  if (failed) return label("agentControls.cost.unavailable");
  if (pricing === "unpriced") return label("agentControls.cost.unpriced");
  if (value == null) return label("agentControls.cost.notTracked");
  if (pricing === "partially_unpriced") {
    return `$${value} (${label("agentControls.cost.partial")})`;
  }
  return `$${value}`;
}

export function AgentControlsSettings({
  client,
  sessionId = null,
  sessionOwned = false,
  sessionContext = null,
  onContextBound,
  projection,
  loading,
  failed,
  permissionModeDraft,
  onPermissionModeChange,
  onRefresh,
  sessionCost = null,
  monthlyCost = null,
  costLoading = false,
  costFailed = false,
  sessionCostLoading,
  monthlyCostLoading,
  sessionCostFailed,
  monthlyCostFailed,
}: Props) {
  const { t } = useTranslation();
  const sessionLoading = sessionCostLoading ?? costLoading;
  const monthlyLoading = monthlyCostLoading ?? costLoading;
  const sessionFailed = sessionCostFailed ?? costFailed;
  const monthlyFailed = monthlyCostFailed ?? costFailed;
  const [contexts, setContexts] = useState<WorkspaceContext[] | null>(null);
  const [contextProblem, setContextProblem] = useState<string | null>(null);
  const [contextBusy, setContextBusy] = useState(false);

  async function refreshContexts(clearProblem = true) {
    if (!client || !sessionId || !sessionOwned) {
      setContexts([]);
      if (clearProblem) setContextProblem(null);
      return;
    }
    try {
      setContexts(await client.listWorkspaceContexts());
      if (clearProblem) setContextProblem(null);
    } catch {
      setContexts([]);
      setContextProblem(t("settings.workspace.unavailable"));
    }
  }

  useEffect(() => {
    setContexts(null);
    void refreshContexts();
  }, [client, sessionId, sessionOwned]);

  async function bindContext(contextId: string) {
    if (!client || !sessionId || !sessionOwned) return;
    setContextBusy(true);
    try {
      await client.bindSessionContext(sessionId, contextId);
      await onContextBound?.();
      await refreshContexts();
    } catch {
      setContextProblem(t("settings.workspace.bindingUnavailable"));
      await refreshContexts(false);
    } finally {
      setContextBusy(false);
    }
  }

  const bindableContexts = (contexts ?? []).filter((context) =>
    context.actions.includes("bind"),
  );

  return (
    <section
      className="capability-section agent-controls-settings"
      aria-labelledby="agent-controls-settings-title"
    >
      <div className="capability-section-heading">
        <div>
          <h2 id="agent-controls-settings-title">
            {t("agentControls.title")}
          </h2>
          <p>{t("agentControls.description")}</p>
        </div>
        {projection ? (
          <button type="button" onClick={onRefresh}>
            {t("agentControls.refresh")}
          </button>
        ) : null}
      </div>

      {loading ? (
        <p className="settings-state" role="status">
          {t("agentControls.loading")}
        </p>
      ) : failed ? (
        <p className="settings-state settings-state-error" role="alert">
          {t("agentControls.unavailable")}
        </p>
      ) : !projection ? (
        <p className="settings-state">{t("agentControls.sessionRequired")}</p>
      ) : (
        <div className="agent-controls-grid">
          <section className="agent-control-card" aria-labelledby="permission-posture-title">
            <h3 id="permission-posture-title">
              {t("agentControls.permission.title")}
            </h3>
            <dl className="agent-control-facts">
              <div>
                <dt>{t("agentControls.permission.default")}</dt>
                <dd>
                  {projection.permission.default_mode ??
                    t("agentControls.permission.hostDefault")}
                </dd>
              </div>
              <div>
                <dt>{t("agentControls.permission.active")}</dt>
                <dd>
                  {postureMode(
                    projection.permission.active_run,
                    t("agentControls.notAvailable"),
                  )}
                </dd>
              </div>
              <div>
                <dt>{t("agentControls.permission.lastAccepted")}</dt>
                <dd>
                  {postureMode(
                    projection.permission.last_accepted_run,
                    t("agentControls.notAvailable"),
                  )}
                </dd>
              </div>
              <div>
                <dt>{t("agentControls.permission.ruleDefault")}</dt>
                <dd>
                  {projection.permission.rule_default ??
                    t("agentControls.notAvailable")}
                </dd>
              </div>
            </dl>

            {permissionModeDraft ? (
              <p className="agent-control-draft" role="status">
                {t("agentControls.permission.draft")}: {permissionModeDraft}
              </p>
            ) : null}

            {projection.actions.includes("select_permission_mode") &&
            projection.permission.selectable_modes.length ? (
              <label className="agent-control-field">
                <span>{t("agentControls.permission.nextRun")}</span>
                <select
                  value={permissionModeDraft ?? ""}
                  onChange={(event) =>
                    onPermissionModeChange(event.target.value || null)
                  }
                >
                  <option value="">
                    {t("agentControls.permission.hostDefault")}
                  </option>
                  {projection.permission.selectable_modes.map((mode) => (
                    <option key={mode.id} value={mode.id}>
                      {mode.id}
                    </option>
                  ))}
                </select>
              </label>
            ) : (
              <p className="settings-state">
                {t("agentControls.permission.readOnly")}
              </p>
            )}

            {projection.permission.plan_exit_requires_approval ? (
              <p className="agent-control-note">
                {t("agentControls.permission.planExitApproval")}
              </p>
            ) : null}
          </section>

          <section className="agent-control-card" aria-labelledby="workspace-context-title">
            <h3 id="workspace-context-title">
              {t("agentControls.context.title")}
            </h3>
            {!sessionOwned ? (
              <p className="settings-state">
                {t("settings.workspace.sessionRequired")}
              </p>
            ) : (
              <>
                <dl className="agent-control-facts">
                  <div>
                    <dt>{t("agentControls.context.current")}</dt>
                    <dd>
                      {sessionContext?.context_name ??
                        t("agentControls.context.unbound")}
                    </dd>
                  </div>
                  {sessionContext?.context_workspace_label ? (
                    <div>
                      <dt>{t("settings.workspace.label")}</dt>
                      <dd>{sessionContext.context_workspace_label}</dd>
                    </div>
                  ) : null}
                  {sessionContext?.context_status ? (
                    <div>
                      <dt>{t("settings.detail.status")}</dt>
                      <dd>{sessionContext.context_status}</dd>
                    </div>
                  ) : null}
                </dl>
                <h4>{t("agentControls.context.available")}</h4>
                {contextProblem ? (
                  <p className="capability-problem" role="alert">
                    {contextProblem}
                  </p>
                ) : null}
                {contexts === null ? (
                  <p className="settings-state" role="status">
                    {t("settings.loading")}
                  </p>
                ) : bindableContexts.length === 0 ? (
                  <p className="settings-state">
                    {t("agentControls.context.noneAvailable")}
                  </p>
                ) : (
                  <ul className="capability-list agent-control-context-list">
                    {bindableContexts.map((context) => (
                      <li className="capability-item" key={context.id}>
                        <div className="capability-item-copy">
                          <strong>{context.name}</strong>
                          <span>{context.workspace_label}</span>
                        </div>
                        {context.scope === "shared_read_only" ||
                        context.status === "read_only" ? (
                          <span className="settings-state">
                            {t("settings.readOnly")}
                          </span>
                        ) : null}
                        <button
                          type="button"
                          disabled={contextBusy}
                          onClick={() => void bindContext(context.id)}
                        >
                          {t("settings.action.bind")}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </>
            )}
          </section>

          <section className="agent-control-card" aria-labelledby="cost-budget-title">
            <h3 id="cost-budget-title">{t("agentControls.cost.title")}</h3>
            <dl className="agent-control-facts">
              <div>
                <dt>{t("agentControls.cost.session")}</dt>
                <dd>
                  {costText(
                    sessionCost?.usd_spent,
                    projection.budget.pricing,
                    sessionLoading,
                    sessionFailed,
                    t,
                  )}
                </dd>
              </div>
              <div>
                <dt>{t("agentControls.cost.monthly")}</dt>
                <dd>
                  {costText(
                    monthlyCost?.usd_spent,
                    projection.budget.pricing,
                    monthlyLoading,
                    monthlyFailed,
                    t,
                  )}
                </dd>
              </div>
              <div>
                <dt>{t("agentControls.cost.pricing")}</dt>
                <dd>{projection.budget.pricing}</dd>
              </div>
              <div>
                <dt>{t("agentControls.cost.tracking")}</dt>
                <dd>{projection.budget.tracking}</dd>
              </div>
              <div>
                <dt>{t("agentControls.cost.messageGuard")}</dt>
                <dd>{projection.budget.message_guard}</dd>
              </div>
              <div>
                <dt>{t("agentControls.cost.sessionGuard")}</dt>
                <dd>{projection.budget.session_guard}</dd>
              </div>
              <div>
                <dt>{t("agentControls.cost.monthlyGuard")}</dt>
                <dd>{projection.budget.monthly_guard}</dd>
              </div>
              <div>
                <dt>{t("agentControls.cost.preTurnGuard")}</dt>
                <dd>{projection.budget.pre_turn_guard}</dd>
              </div>
            </dl>
          </section>
        </div>
      )}
    </section>
  );
}
