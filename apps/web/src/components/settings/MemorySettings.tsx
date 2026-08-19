import { useMemo } from "react";

import {
  MemorySettings as SharedMemorySettings,
  type MemorySettingsService,
} from "@loopplane/cowork-presentation";

import type { ApiClient } from "../../api/client";
import { I18nProvider } from "../../i18n/i18n";

/** Web-only adapter for the shared renderer; HTTP/client ownership remains outside the package. */
export function MemorySettings({
  client,
  canMutate,
}: {
  client: ApiClient;
  canMutate: boolean;
}) {
  const service = useMemo<MemorySettingsService>(
    () => ({
      list: () => client.listMemoryEntries(),
      get: (id) => client.getMemoryEntry(id),
      write: (input) =>
        client.writeMemoryEntry(input).then((response) => response.result),
      remove: (id) => client.deleteMemoryEntry(id),
    }),
    [client],
  );
  return (
    <I18nProvider>
      <SharedMemorySettings service={service} canMutate={canMutate} />
    </I18nProvider>
  );
}
