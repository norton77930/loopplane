import { useEffect, useState } from "react";

import { useTranslation } from "../../i18n/i18n";
import type { PresentationAgentControls } from "../../models";

export interface SessionContextSummary { context_id?: string | null; context_name?: string | null; context_workspace_label?: string | null; context_status?: string | null; }
export interface AgentControlsProjection {
  permission: { default_mode: string | null; selectable_modes: Array<{ id: string }>; rule_default: string | null; plan_exit_requires_approval: boolean; active_run: { mode: string } | null; last_accepted_run: { mode: string } | null; };
  budget: { pricing: string; tracking: string; message_guard: string; session_guard: string; monthly_guard: string; pre_turn_guard: string; };
  actions: string[];
}
export interface SessionCost { usd_spent: string | null; }
export interface WorkspaceContext { id: string; name: string; workspace_label: string; scope: string; status: string; actions: string[]; }
export interface AgentControlsService { listContexts(): Promise<WorkspaceContext[]>; bindContext(sessionId: string, contextId: string): Promise<unknown>; }

export interface AgentControlsSettingsProps {
  service?: AgentControlsService;
  sessionId?: string | null; sessionOwned?: boolean; sessionContext?: SessionContextSummary | null;
  onContextBound?: () => void | Promise<void>; projection: AgentControlsProjection | null; /** Transport-neutral host projection for non-Web adapters. */ hostProjection?: PresentationAgentControls | null; loading: boolean; failed: boolean;
  permissionModeDraft: string | null; onPermissionModeChange: (mode: string | null) => void; onRefresh: () => void;
  sessionCost?: SessionCost | null; monthlyCost?: SessionCost | null; costLoading?: boolean; costFailed?: boolean;
  sessionCostLoading?: boolean; monthlyCostLoading?: boolean; sessionCostFailed?: boolean; monthlyCostFailed?: boolean;
}

function postureMode(posture: { mode: string } | null, unavailable: string) { return posture?.mode ?? unavailable; }
function costText(value: string | null | undefined, pricing: string, loading: boolean, failed: boolean, label: (key: string) => string) {
  if (loading) return label("agentControls.cost.loading"); if (failed) return label("agentControls.cost.unavailable"); if (pricing === "unpriced") return label("agentControls.cost.unpriced"); if (value == null) return label("agentControls.cost.notTracked"); return pricing === "partially_unpriced" ? `$${value} (${label("agentControls.cost.partial")})` : `$${value}`;
}

export function AgentControlsSettings({ service, sessionId = null, sessionOwned = false, sessionContext = null, onContextBound, projection, hostProjection = null, loading, failed, permissionModeDraft, onPermissionModeChange, onRefresh, sessionCost = null, monthlyCost = null, costLoading = false, costFailed = false, sessionCostLoading, monthlyCostLoading, sessionCostFailed, monthlyCostFailed }: AgentControlsSettingsProps) {
  const { t } = useTranslation();
  const displayedProjection: AgentControlsProjection | null = hostProjection ? {
    permission: {
      default_mode: hostProjection.defaultMode,
      selectable_modes: hostProjection.selectableModes.map(({ id }) => ({ id })),
      rule_default: null,
      plan_exit_requires_approval: false,
      active_run: hostProjection.activeRun ? { mode: hostProjection.activeRun.mode } : null,
      last_accepted_run: hostProjection.lastAcceptedRun ? { mode: hostProjection.lastAcceptedRun.mode } : null,
    },
    budget: {
      tracking: hostProjection.budget.tracking,
      pricing: hostProjection.budget.pricing,
      message_guard: "unknown",
      session_guard: hostProjection.budget.sessionGuard,
      monthly_guard: hostProjection.budget.monthlyGuard,
      pre_turn_guard: "unknown",
    },
    actions: hostProjection.actions,
  } : projection;
  const sessionLoading = sessionCostLoading ?? costLoading; const monthlyLoading = monthlyCostLoading ?? costLoading; const sessionFailed = sessionCostFailed ?? costFailed; const monthlyFailed = monthlyCostFailed ?? costFailed;
  const [contexts, setContexts] = useState<WorkspaceContext[] | null>(null); const [contextProblem, setContextProblem] = useState<string | null>(null); const [contextBusy, setContextBusy] = useState(false);
  async function refreshContexts(clearProblem = true) {
    if (!service || !sessionId || !sessionOwned) { setContexts([]); if (clearProblem) setContextProblem(null); return; }
    try { setContexts(await service.listContexts()); if (clearProblem) setContextProblem(null); } catch { setContexts([]); setContextProblem(t("settings.workspace.unavailable")); }
  }
  useEffect(() => { setContexts(null); void refreshContexts(); }, [service, sessionId, sessionOwned]);
  async function bindContext(contextId: string) {
    if (!service || !sessionId || !sessionOwned) return; setContextBusy(true);
    try { await service.bindContext(sessionId, contextId); await onContextBound?.(); await refreshContexts(); } catch { setContextProblem(t("settings.workspace.bindingUnavailable")); await refreshContexts(false); } finally { setContextBusy(false); }
  }
  const bindableContexts = (contexts ?? []).filter((context) => context.actions.includes("bind"));
  return <section className="capability-section agent-controls-settings" aria-labelledby="agent-controls-settings-title"><div className="capability-section-heading"><div><h2 id="agent-controls-settings-title">{t("agentControls.title")}</h2><p>{t("agentControls.description")}</p></div>{displayedProjection ? <button type="button" onClick={onRefresh}>{t("agentControls.refresh")}</button> : null}</div>
    {loading ? <p className="settings-state" role="status">{t("agentControls.loading")}</p> : failed || hostProjection?.unavailable ? <p className="settings-state settings-state-error" role="alert">{t("agentControls.unavailable")}</p> : !displayedProjection ? <p className="settings-state">{t("agentControls.sessionRequired")}</p> : <div className="agent-controls-grid">
      <section className="agent-control-card" aria-labelledby="permission-posture-title"><h3 id="permission-posture-title">{t("agentControls.permission.title")}</h3><dl className="agent-control-facts"><div><dt>{t("agentControls.permission.default")}</dt><dd>{displayedProjection.permission.default_mode ?? t("agentControls.permission.hostDefault")}</dd></div><div><dt>{t("agentControls.permission.active")}</dt><dd>{postureMode(displayedProjection.permission.active_run, t("agentControls.notAvailable"))}</dd></div><div><dt>{t("agentControls.permission.lastAccepted")}</dt><dd>{postureMode(displayedProjection.permission.last_accepted_run, t("agentControls.notAvailable"))}</dd></div><div><dt>{t("agentControls.permission.ruleDefault")}</dt><dd>{displayedProjection.permission.rule_default ?? t("agentControls.notAvailable")}</dd></div></dl>{permissionModeDraft ? <p className="agent-control-draft" role="status">{t("agentControls.permission.draft")}: {permissionModeDraft}</p> : null}{displayedProjection.actions.includes("select_permission_mode") && displayedProjection.permission.selectable_modes.length ? <label className="agent-control-field"><span>{t("agentControls.permission.nextRun")}</span><select value={permissionModeDraft ?? ""} onChange={(event) => onPermissionModeChange(event.target.value || null)}><option value="">{t("agentControls.permission.hostDefault")}</option>{displayedProjection.permission.selectable_modes.map((mode) => <option key={mode.id} value={mode.id}>{mode.id}</option>)}</select></label> : <p className="settings-state">{t("agentControls.permission.readOnly")}</p>}{displayedProjection.permission.plan_exit_requires_approval ? <p className="agent-control-note">{t("agentControls.permission.planExitApproval")}</p> : null}</section>
      <section className="agent-control-card" aria-labelledby="workspace-context-title"><h3 id="workspace-context-title">{t("agentControls.context.title")}</h3>{!sessionOwned ? <p className="settings-state">{t("settings.workspace.sessionRequired")}</p> : <><dl className="agent-control-facts"><div><dt>{t("agentControls.context.current")}</dt><dd>{sessionContext?.context_name ?? t("agentControls.context.unbound")}</dd></div>{sessionContext?.context_workspace_label ? <div><dt>{t("settings.workspace.label")}</dt><dd>{sessionContext.context_workspace_label}</dd></div> : null}{sessionContext?.context_status ? <div><dt>{t("settings.detail.status")}</dt><dd>{sessionContext.context_status}</dd></div> : null}</dl><h4>{t("agentControls.context.available")}</h4>{contextProblem ? <p className="capability-problem" role="alert">{contextProblem}</p> : null}{contexts === null ? <p className="settings-state" role="status">{t("settings.loading")}</p> : bindableContexts.length === 0 ? <p className="settings-state">{t("agentControls.context.noneAvailable")}</p> : <ul className="capability-list agent-control-context-list">{bindableContexts.map((context) => <li className="capability-item" key={context.id}><div className="capability-item-copy"><strong>{context.name}</strong><span>{context.workspace_label}</span></div>{context.scope === "shared_read_only" || context.status === "read_only" ? <span className="settings-state">{t("settings.readOnly")}</span> : null}<button type="button" disabled={contextBusy} onClick={() => void bindContext(context.id)}>{t("settings.action.bind")}</button></li>)}</ul>}</>}</section>
      <section className="agent-control-card" aria-labelledby="cost-budget-title"><h3 id="cost-budget-title">{t("agentControls.cost.title")}</h3><dl className="agent-control-facts"><div><dt>{t("agentControls.cost.session")}</dt><dd>{costText(sessionCost?.usd_spent, displayedProjection.budget.pricing, sessionLoading, sessionFailed, t)}</dd></div><div><dt>{t("agentControls.cost.monthly")}</dt><dd>{costText(monthlyCost?.usd_spent, displayedProjection.budget.pricing, monthlyLoading, monthlyFailed, t)}</dd></div><div><dt>{t("agentControls.cost.pricing")}</dt><dd>{displayedProjection.budget.pricing}</dd></div><div><dt>{t("agentControls.cost.tracking")}</dt><dd>{displayedProjection.budget.tracking}</dd></div><div><dt>{t("agentControls.cost.messageGuard")}</dt><dd>{displayedProjection.budget.message_guard}</dd></div><div><dt>{t("agentControls.cost.sessionGuard")}</dt><dd>{displayedProjection.budget.session_guard}</dd></div><div><dt>{t("agentControls.cost.monthlyGuard")}</dt><dd>{displayedProjection.budget.monthly_guard}</dd></div><div><dt>{t("agentControls.cost.preTurnGuard")}</dt><dd>{displayedProjection.budget.pre_turn_guard}</dd></div></dl></section>
    </div>}</section>;
}
