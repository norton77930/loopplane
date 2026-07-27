import { useEffect, useState } from "react";

import type { ApiClient } from "../api/client";
import type {
  AgentControlProjection,
  CapabilitySettingsStatus,
  MonthlyCostView,
  SessionCostView,
} from "../api/types";
import { useTranslation } from "../i18n/i18n";
import {
  AgentControlsSettings,
  type SessionContextSummary,
} from "./settings/AgentControlsSettings";
import { McpSettings } from "./settings/McpSettings";
import { MemorySettings } from "./settings/MemorySettings";
import { ModelDefaultSettings } from "./settings/ModelDefaultSettings";
import { ScheduleSettings } from "./settings/ScheduleSettings";
import { SettingsLayout } from "./settings/SettingsLayout";
import { SkillSettings } from "./settings/SkillSettings";
import { WorkspaceSettings } from "./settings/WorkspaceSettings";

type SettingsTab =
  | "agent-controls"
  | "memory"
  | "skills"
  | "mcp"
  | "workspace"
  | "schedules"
  | "model-default";

const TABS: Array<{ id: SettingsTab; labelKey: string }> = [
  { id: "agent-controls", labelKey: "settings.tab.agentControls" },
  { id: "memory", labelKey: "settings.tab.memory" },
  { id: "skills", labelKey: "settings.tab.skills" },
  { id: "mcp", labelKey: "settings.tab.mcp" },
  { id: "workspace", labelKey: "settings.tab.workspace" },
  { id: "schedules", labelKey: "settings.tab.schedules" },
  { id: "model-default", labelKey: "settings.tab.modelDefault" },
];

export function CapabilitySettingsView({
  client,
  sessionId,
  sessionOwned = false,
  sessionContext = null,
  agentControls = null,
  agentControlsLoading = false,
  agentControlsFailed = false,
  permissionModeDraft = null,
  onPermissionModeChange = () => undefined,
  onAgentControlsRefresh = () => undefined,
  sessionCost = null,
  monthlyCost = null,
  sessionCostLoading = false,
  monthlyCostLoading = false,
  sessionCostFailed = false,
  monthlyCostFailed = false,
  onContextBound,
  onBack,
}: {
  client: ApiClient;
  sessionId?: string | null;
  sessionOwned?: boolean;
  sessionContext?: SessionContextSummary | null;
  agentControls?: AgentControlProjection | null;
  agentControlsLoading?: boolean;
  agentControlsFailed?: boolean;
  permissionModeDraft?: string | null;
  onPermissionModeChange?: (mode: string | null) => void;
  onAgentControlsRefresh?: () => void;
  sessionCost?: SessionCostView | null;
  monthlyCost?: MonthlyCostView | null;
  sessionCostLoading?: boolean;
  monthlyCostLoading?: boolean;
  sessionCostFailed?: boolean;
  monthlyCostFailed?: boolean;
  onContextBound?: () => void;
  onBack?: () => void;
}) {
  const { t } = useTranslation();
  const [tab, setTab] = useState<SettingsTab>("memory");
  const [status, setStatus] = useState<CapabilitySettingsStatus | null>(null);
  const [statusFailed, setStatusFailed] = useState(false);

  useEffect(() => {
    let live = true;
    void client
      .getCapabilitySettings()
      .then((next) => {
        if (live) {
          setStatus(next);
          setStatusFailed(false);
        }
      })
      .catch(() => {
        if (live) {
          setStatus(null);
          setStatusFailed(true);
        }
      });
    return () => {
      live = false;
    };
  }, [client]);

  const canMutate = Boolean(
    status?.storage_available && status.mutations_enabled,
  );

  return (
    <SettingsLayout
      title={t("settings.title")}
      status={
        statusFailed ? (
          <span className="settings-state settings-state-error" role="alert">
            {t("settings.statusUnavailable")}
          </span>
        ) : !status ? (
          <span className="settings-state" role="status">
            {t("settings.loading")}
          </span>
        ) : !status.mutations_enabled ? (
          <span className="settings-state">{t("settings.readOnly")}</span>
        ) : undefined
      }
      items={TABS.map((entry) => ({ id: entry.id, label: t(entry.labelKey) }))}
      activeId={tab}
      onSelect={(id) => setTab(id as SettingsTab)}
      onBack={onBack}
      backLabel={t("settings.back")}
    >
        {tab === "agent-controls" && (
          <AgentControlsSettings
            client={client}
            sessionId={sessionId}
            sessionOwned={sessionOwned}
            sessionContext={sessionContext}
            onContextBound={onContextBound}
            projection={agentControls}
            loading={agentControlsLoading}
            failed={agentControlsFailed}
            permissionModeDraft={permissionModeDraft}
            onPermissionModeChange={onPermissionModeChange}
            onRefresh={onAgentControlsRefresh}
            sessionCost={sessionCost}
            monthlyCost={monthlyCost}
            sessionCostLoading={sessionCostLoading}
            monthlyCostLoading={monthlyCostLoading}
            sessionCostFailed={sessionCostFailed}
            monthlyCostFailed={monthlyCostFailed}
          />
        )}
        {tab === "memory" && (
          <MemorySettings client={client} canMutate={canMutate} />
        )}
        {tab === "skills" && (
          <SkillSettings client={client} canMutate={canMutate} />
        )}
        {tab === "mcp" && (
          <McpSettings client={client} canMutate={canMutate} />
        )}
        {tab === "workspace" && (
          <WorkspaceSettings
            client={client}
            canMutate={canMutate}
            sessionId={sessionId}
            onContextBound={onContextBound}
          />
        )}
        {tab === "schedules" && (
          <ScheduleSettings client={client} canMutate={canMutate} />
        )}
        {tab === "model-default" && (
          <ModelDefaultSettings client={client} canMutate={canMutate} />
        )}
    </SettingsLayout>
  );
}
