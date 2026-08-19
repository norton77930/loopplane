import { useMemo } from "react";

import {
  ModelDefaultSettings as SharedModelDefaultSettings,
  type ModelDefaultSettingsService,
} from "@loopplane/cowork-presentation";

import type { ApiClient } from "../../api/client";
import { I18nProvider } from "../../i18n/i18n";

/** Web-only adapter for the shared renderer; HTTP/client ownership remains outside the package. */
export function ModelDefaultSettings({
  client,
  canMutate,
}: {
  client: ApiClient;
  canMutate: boolean;
}) {
  const service = useMemo<ModelDefaultSettingsService>(
    () => ({
      listModels: () => client.listModels(),
      getDefault: () => client.getModelDefault(),
      setDefault: (modelId) =>
        client.setModelDefault(modelId).then((response) => response.result),
      clearDefault: () =>
        client.clearModelDefault().then((response) => response.result),
    }),
    [client],
  );
  return (
    <I18nProvider>
      <SharedModelDefaultSettings service={service} canMutate={canMutate} />
    </I18nProvider>
  );
}
