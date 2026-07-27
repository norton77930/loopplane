import type { Ref } from "react";

import { useTranslation } from "../i18n/i18n";
import type { ChatState, UsageState } from "../state/chat";
import { LanguageSwitcher } from "./LanguageSwitcher";
import { ThemeToggle } from "./ThemeToggle";
import { UsageIndicator } from "./UsageIndicator";
import { MenuIcon, PanelRightIcon, SettingsIcon } from "./icons/Icons";

// The sticky chat header: a localized status indicator (FR-009; 029 i18n), the token-usage +
// authoritative server-cost indicator (026/064/077), an Inspect toggle (027), a Stop control while running, the
// language switcher (029), and the theme toggle.
const LABEL_KEY: Record<ChatState["status"], string> = {
  idle: "header.idle",
  running: "header.running",
  terminated: "header.terminated",
  error: "header.error",
};

interface Props {
  status: ChatState["status"];
  usage: UsageState;
  cost?: string | null;
  onStop: () => void;
  inspectOpen: boolean;
  onToggleInspect: () => void;
  settingsOpen?: boolean;
  onToggleSettings?: () => void;
  contextName?: string | null;
  onToggleNavigation?: () => void;
  modelName?: string | null;
  navigationOpen?: boolean;
  settingsButtonRef?: Ref<HTMLButtonElement>;
  inspectButtonRef?: Ref<HTMLButtonElement>;
}

export function ChatHeader({
  status,
  usage,
  cost,
  onStop,
  inspectOpen,
  onToggleInspect,
  settingsOpen = false,
  onToggleSettings,
  contextName,
  onToggleNavigation,
  modelName,
  navigationOpen = false,
  settingsButtonRef,
  inspectButtonRef,
}: Props) {
  const { t } = useTranslation();
  return (
    <header className="chat-header">
      {onToggleNavigation && (
        <button
          type="button"
          className="navigation-toggle"
          aria-label={t(navigationOpen ? "navigation.close" : "navigation.open")}
          aria-controls="session-navigation"
          aria-expanded={navigationOpen}
          onClick={onToggleNavigation}
        >
          <MenuIcon />
        </button>
      )}
      <div className="chat-header-main">
        <span className="brand">LoopPlane</span>
        <span
          className="status"
          data-status={status}
          role="status"
          aria-live="polite"
          aria-atomic="true"
        >
          <span className="dot" aria-hidden="true" />
          {t(LABEL_KEY[status])}
        </span>
        {modelName && <span className="active-model">Active model: {modelName}</span>}
        <UsageIndicator usage={usage} cost={cost} />
        {contextName && (
          <span className="session-context">Context: {contextName}</span>
        )}
      </div>
      <div className="chat-header-actions">
        {status === "running" && (
          <button type="button" className="danger" onClick={onStop}>
            {t("header.stop")}
          </button>
        )}
        <button
          type="button"
          ref={settingsButtonRef}
          className={settingsOpen ? "active" : ""}
          aria-pressed={settingsOpen}
          onClick={onToggleSettings}
        >
          <SettingsIcon />
          <span className="action-label">{t("header.settings")}</span>
        </button>
        <button
          type="button"
          ref={inspectButtonRef}
          className={inspectOpen ? "active" : ""}
          aria-pressed={inspectOpen}
          onClick={onToggleInspect}
        >
          <PanelRightIcon />
          <span className="action-label">{t("header.inspect")}</span>
        </button>
        <LanguageSwitcher />
        <ThemeToggle />
      </div>
    </header>
  );
}
