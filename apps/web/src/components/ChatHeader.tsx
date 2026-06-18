import type { ChatState, UsageState } from "../state/chat";
import { ThemeToggle } from "./ThemeToggle";
import { UsageIndicator } from "./UsageIndicator";

// The sticky chat header (FR-009; 026): a connection/run status indicator, the token-usage
// indicator (026), a Stop control while a run is in flight, and the theme toggle.
const LABEL: Record<ChatState["status"], string> = {
  idle: "Idle",
  running: "Running",
  terminated: "Ended",
  error: "Disconnected",
};

interface Props {
  status: ChatState["status"];
  usage: UsageState;
  onStop: () => void;
}

export function ChatHeader({ status, usage, onStop }: Props) {
  return (
    <header className="chat-header">
      <span className="brand">LoopPlane</span>
      <span className="status" data-status={status}>
        <span className="dot" aria-hidden="true" />
        {LABEL[status]}
      </span>
      <UsageIndicator usage={usage} />
      <span className="spacer" />
      {status === "running" && (
        <button type="button" className="danger" onClick={onStop}>
          Stop
        </button>
      )}
      <ThemeToggle />
    </header>
  );
}
