import {
  AgentControlsSettings as SharedAgentControlsSettings,
  type SessionContextSummary,
} from "@loopplane/cowork-presentation";

import type { ApiClient } from "../../api/client";
import { I18nProvider } from "../../i18n/i18n";
import type {
  AgentControlProjection,
  MonthlyCostView,
  SessionCostView,
} from "../../api/types";

export type { SessionContextSummary };

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

/** Web-only adapter for the shared renderer; HTTP/client ownership remains outside the package. */
export function AgentControlsSettings({ client, ...props }: Props) {
  const service = client ? {
    listContexts: () => client.listWorkspaceContexts(),
    bindContext: (sessionId: string, contextId: string) => client.bindSessionContext(sessionId, contextId),
  } : undefined;
  return <I18nProvider><SharedAgentControlsSettings service={service} {...props} /></I18nProvider>;
}
