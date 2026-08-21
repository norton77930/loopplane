import { useMemo } from "react";

import {
  McpSettings as SharedMcpSettings,
  type McpSettingsService,
} from "@loopplane/cowork-presentation";

import type { ApiClient } from "../../api/client";
import { I18nProvider } from "../../i18n/i18n";

/** Web-only adapter for the shared renderer; HTTP/client ownership remains outside the package. */
export function McpSettings({
  client,
  canMutate,
}: {
  client: ApiClient;
  canMutate: boolean;
}) {
  // Memoized on the client so the shared panel's refresh effect keeps the exact
  // cadence the pre-extraction `[client]` dependency had.
  const service = useMemo<McpSettingsService>(
    () => ({
      list: () => client.listMcpConfigurations(),
      get: (id) => client.getMcpConfiguration(id),
      upsert: (input) =>
        client.upsertMcpConfiguration(input).then((response) => response.result),
      reconnect: (id) => client.reconnectMcpConfiguration(id),
      remove: (id) => client.deleteMcpConfiguration(id),
    }),
    [client],
  );
  return (
    <I18nProvider>
      <SharedMcpSettings service={service} canMutate={canMutate} />
    </I18nProvider>
  );
}
