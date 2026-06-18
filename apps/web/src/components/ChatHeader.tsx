import { useTranslation } from "../i18n/i18n";
import type { ChatState, UsageState } from "../state/chat";
import { LanguageSwitcher } from "./LanguageSwitcher";
import { ThemeToggle } from "./ThemeToggle";
import { UsageIndicator } from "./UsageIndicator";

// The sticky chat header: a localized status indicator (FR-009; 029 i18n), the token-usage +
// estimated-cost indicator (026/029), an Inspect toggle (027), a Stop control while running, the
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
  cost?: number | null;
  onStop: () => void;
  inspectOpen: boolean;
  onToggleInspect: () => void;
}

export function ChatHeader({ status, usage, cost, onStop, inspectOpen, onToggleInspect }: Props) {
  const { t } = useTranslation();
  return (
    <header className="chat-header">
      <span className="brand">LoopPlane</span>
      <span className="status" data-status={status}>
        <span className="dot" aria-hidden="true" />
        {t(LABEL_KEY[status])}
      </span>
      <UsageIndicator usage={usage} cost={cost} />
      <span className="spacer" />
      {status === "running" && (
        <button type="button" className="danger" onClick={onStop}>
          {t("header.stop")}
        </button>
      )}
      <button
        type="button"
        className={inspectOpen ? "active" : ""}
        aria-pressed={inspectOpen}
        onClick={onToggleInspect}
      >
        {t("header.inspect")}
      </button>
      <LanguageSwitcher />
      <ThemeToggle />
    </header>
  );
}
