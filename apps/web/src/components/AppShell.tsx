import { AppShell as SharedAppShell, type AppShellProps } from "@loopplane/cowork-presentation";
import { I18nProvider } from "../i18n/i18n";
export type { AppShellProps as Props } from "@loopplane/cowork-presentation";
export function AppShell(props: AppShellProps) { return <I18nProvider><SharedAppShell {...props} /></I18nProvider>; }
