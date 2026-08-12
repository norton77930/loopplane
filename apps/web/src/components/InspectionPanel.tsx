import { InspectionPanel as SharedInspectionPanel, type InspectionLoaders } from "@loopplane/cowork-presentation";
import type { ApiClient } from "../api/client";
import type { WebPresentationHost } from "../presentation-host";
import { I18nProvider } from "../i18n/i18n";

/** Web-only projection adapter. App passes its host, never host.webClient to shared UI. */
export function InspectionPanel({ client, host }: { client?: ApiClient; host?: WebPresentationHost }) {
  const source = client ?? host?.webClient;
  if (!source) return null;
  const loaders: InspectionLoaders = {
    inspectSkills: () => source.inspectSkills(),
    inspectTools: () => source.inspectTools(),
    inspectMcp: () => source.inspectMcp(),
    inspectMemory: (query) => source.inspectMemory(query),
  };
  return <I18nProvider><SharedInspectionPanel loaders={loaders} /></I18nProvider>;
}
