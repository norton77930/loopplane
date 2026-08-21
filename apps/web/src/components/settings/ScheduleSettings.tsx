import { useMemo } from "react";

import {
  ScheduleSettings as SharedScheduleSettings,
  type ScheduleSettingsService,
} from "@loopplane/cowork-presentation";

import type { ApiClient } from "../../api/client";
import { I18nProvider } from "../../i18n/i18n";

/** Web-only adapter for the shared renderer; HTTP/client ownership remains outside the package. */
export function ScheduleSettings({
  client,
  canMutate,
}: {
  client: ApiClient;
  canMutate: boolean;
}) {
  const service = useMemo<ScheduleSettingsService>(
    () => ({
      list: () => client.listSchedules(),
      get: (id) => client.getSchedule(id),
      upsert: (input) =>
        client.upsertSchedule(input).then((response) => response.result),
      runNow: (id) => client.runScheduleNow(id),
      enable: (id) => client.enableSchedule(id),
      disable: (id) => client.disableSchedule(id),
      remove: (id) => client.deleteSchedule(id),
    }),
    [client],
  );
  return (
    <I18nProvider>
      <SharedScheduleSettings service={service} canMutate={canMutate} />
    </I18nProvider>
  );
}
