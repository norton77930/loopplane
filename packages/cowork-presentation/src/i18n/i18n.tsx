import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export type TranslationMessages = Record<string, Record<string, string>>;

export interface Translation {
  t: (key: string) => string;
  locale: string;
  setLocale: (locale: string) => void;
}

const fallbackMessages: TranslationMessages = {
  en: {
    "navigation.label": "Session navigation",
    "navigation.close": "Close session navigation",
    "inspection.panel": "Inspection panel",
    "inspection.dismiss": "Dismiss inspection panel",
    "inspection.close": "Close inspection panel",
    "inspection.categories": "Inspection categories",
    "inspection.tab.skills": "Skills",
    "inspection.tab.tools": "Tools",
    "inspection.tab.mcp": "MCP",
    "inspection.tab.memory": "Memory",
    "inspection.searchMemory": "search memory",
    "inspection.searchMemoryPlaceholder": "Search memory...",
    "inspection.skills.loading": "Loading skills...",
    "inspection.skills.error": "Unable to load skills.",
    "inspection.skills.empty": "No skills to show.",
    "inspection.tools.loading": "Loading tools...",
    "inspection.tools.error": "Unable to load tools.",
    "inspection.tools.empty": "No tools to show.",
    "inspection.mcp.loading": "Loading MCP servers...",
    "inspection.mcp.error": "Unable to load MCP servers.",
    "inspection.mcp.empty": "No MCP servers to show.",
    "inspection.memory.loading": "Loading memory entries...",
    "inspection.memory.error": "Unable to load memory entries.",
    "inspection.memory.empty": "No memory entries to show.",
    "inspection.approval": "approval",
    "inspection.readOnly": "read-only",
    "empty.title": "Start a conversation",
    "agentControls.title": "Agent controls",
    "agentControls.description": "Authoritative execution posture for this session.",
    "agentControls.refresh": "Refresh",
    "agentControls.loading": "Loading agent controls...",
    "agentControls.unavailable": "Agent controls are unavailable.",
    "agentControls.sessionRequired": "Start or open a session to view agent controls.",
    "agentControls.notAvailable": "Not available",
    "agentControls.permission.title": "Plan and permission posture",
    "agentControls.permission.default": "Host default",
    "agentControls.permission.hostDefault": "Use host default",
    "agentControls.permission.active": "Active run",
    "agentControls.permission.lastAccepted": "Last accepted run",
    "agentControls.permission.ruleDefault": "Rule default",
    "agentControls.permission.draft": "Draft for next run",
    "agentControls.permission.nextRun": "Permission mode for next run",
    "agentControls.permission.readOnly": "No permission changes are available.",
    "agentControls.permission.planExitApproval": "Leaving plan mode requires the existing approval flow.",
    "agentControls.context.title": "Workspace context",
    "agentControls.context.current": "Current context",
    "agentControls.context.unbound": "Not bound",
    "agentControls.context.available": "Available contexts",
    "agentControls.context.noneAvailable": "No bindable contexts are available.",
    "agentControls.cost.title": "Cost and budget",
    "agentControls.cost.session": "Session spend",
    "agentControls.cost.monthly": "Monthly spend",
    "agentControls.cost.pricing": "Pricing status",
    "agentControls.cost.tracking": "Tracking status",
    "agentControls.cost.messageGuard": "Message guard",
    "agentControls.cost.sessionGuard": "Session guard",
    "agentControls.cost.monthlyGuard": "Monthly guard",
    "agentControls.cost.preTurnGuard": "Pre-turn guard",
    "agentControls.cost.loading": "Loading",
    "agentControls.cost.unavailable": "Unavailable",
    "agentControls.cost.unpriced": "Unpriced",
    "agentControls.cost.notTracked": "Not tracked",
    "agentControls.cost.partial": "partially priced",
    "settings.workspace.sessionRequired": "Open a session to manage its workspace context.",
    "action.copy": "Copy",
    "action.regenerate": "Regenerate",
  },
};

function lookup(messages: TranslationMessages, key: string, locale: string): string {
  return messages[locale]?.[key] ?? messages.en?.[key] ?? key;
}

const I18nContext = createContext<Translation>({
  t: (key) => lookup(fallbackMessages, key, "en"),
  locale: "en",
  setLocale: () => undefined,
});

export function PresentationI18nProvider({
  children,
  messages = fallbackMessages,
  defaultLocale = "en",
  storageKey,
}: {
  children: ReactNode;
  messages?: TranslationMessages;
  defaultLocale?: string;
  storageKey?: string;
}) {
  const [locale, setLocaleState] = useState(() => {
    try {
      const stored = storageKey ? localStorage.getItem(storageKey) : null;
      return stored && messages[stored] ? stored : defaultLocale;
    } catch {
      return defaultLocale;
    }
  });

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const value = useMemo<Translation>(
    () => ({
      locale,
      t: (key) => lookup(messages, key, locale),
      setLocale(next) {
        if (!messages[next]) return;
        setLocaleState(next);
        try {
          if (storageKey) localStorage.setItem(storageKey, next);
        } catch {
          // Storage is optional presentation state.
        }
      },
    }),
    [locale, messages, storageKey],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useTranslation(): Translation {
  return useContext(I18nContext);
}
