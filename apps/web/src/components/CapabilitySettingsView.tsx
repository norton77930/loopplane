import { useEffect, useState } from "react";
import { CapabilitySettingsView as SharedCapabilitySettingsView } from "@loopplane/cowork-presentation";

import type { ApiClient } from "../api/client";
import type { WebPresentationHost } from "../presentation-host";
import type { AgentControlProjection, CapabilitySettingsStatus, MonthlyCostView, SessionCostView } from "../api/types";
import { I18nProvider, useTranslation } from "../i18n/i18n";
import { AgentControlsSettings, type SessionContextSummary } from "./settings/AgentControlsSettings";
import { McpSettings } from "./settings/McpSettings";
import { MemorySettings } from "./settings/MemorySettings";
import { ModelDefaultSettings } from "./settings/ModelDefaultSettings";
import { ScheduleSettings } from "./settings/ScheduleSettings";
import { SkillSettings } from "./settings/SkillSettings";
import { WorkspaceSettings } from "./settings/WorkspaceSettings";

type SettingsTab = "agent-controls" | "memory" | "skills" | "mcp" | "workspace" | "schedules" | "model-default";
const TABS: Array<{ id: SettingsTab; labelKey: string }> = [
  { id: "agent-controls", labelKey: "settings.tab.agentControls" }, { id: "memory", labelKey: "settings.tab.memory" }, { id: "skills", labelKey: "settings.tab.skills" }, { id: "mcp", labelKey: "settings.tab.mcp" }, { id: "workspace", labelKey: "settings.tab.workspace" }, { id: "schedules", labelKey: "settings.tab.schedules" }, { id: "model-default", labelKey: "settings.tab.modelDefault" },
];

export function CapabilitySettingsView({ client, host, sessionId, sessionOwned = false, sessionContext = null, agentControls = null, agentControlsLoading = false, agentControlsFailed = false, permissionModeDraft = null, onPermissionModeChange = () => undefined, onAgentControlsRefresh = () => undefined, sessionCost = null, monthlyCost = null, sessionCostLoading = false, monthlyCostLoading = false, sessionCostFailed = false, monthlyCostFailed = false, onContextBound, onBack }: { client?: ApiClient; host?: WebPresentationHost; sessionId?: string | null; sessionOwned?: boolean; sessionContext?: SessionContextSummary | null; agentControls?: AgentControlProjection | null; agentControlsLoading?: boolean; agentControlsFailed?: boolean; permissionModeDraft?: string | null; onPermissionModeChange?: (mode: string | null) => void; onAgentControlsRefresh?: () => void; sessionCost?: SessionCostView | null; monthlyCost?: MonthlyCostView | null; sessionCostLoading?: boolean; monthlyCostLoading?: boolean; sessionCostFailed?: boolean; monthlyCostFailed?: boolean; onContextBound?: () => void; onBack?: () => void; }) {
  const { t } = useTranslation();
  const source = client ?? host?.webClient;
  const [status, setStatus] = useState<CapabilitySettingsStatus | null>(null);
  const [statusFailed, setStatusFailed] = useState(false);
  useEffect(() => { if (!source) return; let live = true; void source.getCapabilitySettings().then((next) => { if (live) { setStatus(next); setStatusFailed(false); } }).catch(() => { if (live) { setStatus(null); setStatusFailed(true); } }); return () => { live = false; }; }, [source]);
  if (!source) return null;
  const resolvedClient: ApiClient = source;
  const canMutate = Boolean(status?.storage_available && status.mutations_enabled);
  const sharedStatus = statusFailed ? <span className="settings-state settings-state-error" role="alert">{t("settings.statusUnavailable")}</span> : !status ? <span className="settings-state" role="status">{t("settings.loading")}</span> : !status.mutations_enabled ? <span className="settings-state">{t("settings.readOnly")}</span> : undefined;
  function renderTab(tab: string) {
    switch (tab as SettingsTab) {
      case "agent-controls": return <AgentControlsSettings client={resolvedClient} sessionId={sessionId} sessionOwned={sessionOwned} sessionContext={sessionContext} onContextBound={onContextBound} projection={agentControls} loading={agentControlsLoading} failed={agentControlsFailed} permissionModeDraft={permissionModeDraft} onPermissionModeChange={onPermissionModeChange} onRefresh={onAgentControlsRefresh} sessionCost={sessionCost} monthlyCost={monthlyCost} sessionCostLoading={sessionCostLoading} monthlyCostLoading={monthlyCostLoading} sessionCostFailed={sessionCostFailed} monthlyCostFailed={monthlyCostFailed} />;
      case "memory": return <MemorySettings client={resolvedClient} canMutate={canMutate} />;
      case "skills": return <SkillSettings client={resolvedClient} canMutate={canMutate} />;
      case "mcp": return <McpSettings client={resolvedClient} canMutate={canMutate} />;
      case "workspace": return <WorkspaceSettings client={resolvedClient} canMutate={canMutate} sessionId={sessionId} onContextBound={onContextBound} />;
      case "schedules": return <ScheduleSettings client={resolvedClient} canMutate={canMutate} />;
      case "model-default": return <ModelDefaultSettings client={resolvedClient} canMutate={canMutate} />;
    }
  }
  return <I18nProvider><SharedCapabilitySettingsView title={t("settings.title")} categoriesLabel={t("settings.categories")} backLabel={t("settings.back")} tabs={TABS.map((entry) => ({ id: entry.id, label: t(entry.labelKey) }))} initialTabId="memory" status={sharedStatus} onBack={onBack} renderTab={renderTab} /></I18nProvider>;
}
