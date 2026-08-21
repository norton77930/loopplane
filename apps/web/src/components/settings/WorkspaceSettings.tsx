import { useMemo } from "react";

import {
  WorkspaceSettings as SharedWorkspaceSettings,
  type WorkspaceSettingsService,
} from "@loopplane/cowork-presentation";

import type { ApiClient } from "../../api/client";
import { I18nProvider } from "../../i18n/i18n";

/** Web-only adapter for the shared renderer; HTTP/client ownership remains outside the package. */
export function WorkspaceSettings({
  client,
  canMutate,
  sessionId,
  onContextBound,
}: {
  client: ApiClient;
  canMutate: boolean;
  sessionId?: string | null;
  onContextBound?: () => void | Promise<void>;
}) {
  const service = useMemo<WorkspaceSettingsService>(
    () => ({
      list: () => client.listWorkspaceContexts(),
      get: (id) => client.getWorkspaceContext(id),
      upsert: (input) =>
        client.upsertWorkspaceContext(input).then((response) => response.result),
      bind: (boundSessionId, contextId) =>
        client.bindSessionContext(boundSessionId, contextId),
      remove: (id) => client.deleteWorkspaceContext(id),
    }),
    [client],
  );
  return (
    <I18nProvider>
      <SharedWorkspaceSettings
        service={service}
        canMutate={canMutate}
        sessionId={sessionId}
        onContextBound={onContextBound}
      />
    </I18nProvider>
  );
}
