import { useMemo } from "react";

import {
  SkillSettings as SharedSkillSettings,
  type SkillSettingsService,
} from "@loopplane/cowork-presentation";

import type { ApiClient } from "../../api/client";
import { I18nProvider } from "../../i18n/i18n";

/** Web-only adapter for the shared renderer; HTTP/client ownership remains outside the package. */
export function SkillSettings({
  client,
  canMutate,
}: {
  client: ApiClient;
  canMutate: boolean;
}) {
  const service = useMemo<SkillSettingsService>(
    () => ({
      list: () => client.listManagedSkills(),
      get: (id) => client.getManagedSkill(id),
      write: (definition) =>
        client.writeManagedSkill(definition).then((response) => response.result),
      import: (definition) =>
        client
          .importManagedSkill(definition)
          .then((response) => response.result),
      remove: (id) => client.deleteManagedSkill(id),
    }),
    [client],
  );
  return (
    <I18nProvider>
      <SharedSkillSettings service={service} canMutate={canMutate} />
    </I18nProvider>
  );
}
