import { MessageList as SharedMessageList, type MessageListProps } from "@loopplane/cowork-presentation";
import { I18nProvider } from "../i18n/i18n";
export type { MessageListProps as Props } from "@loopplane/cowork-presentation";
export function MessageList(props: MessageListProps) { return <I18nProvider><SharedMessageList {...props} /></I18nProvider>; }
