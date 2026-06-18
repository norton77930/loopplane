import type { ChatState } from "../state/chat";
import { ThemeToggle } from "./ThemeToggle";

// The sticky chat header (FR-009): a connection/run status indicator, a Stop control while a
// run is in flight, and the theme toggle.
const LABEL: Record<ChatState["status"], string> = {
  idle: "Idle",
  running: "Running",
  terminated: "Ended",
  error: "Disconnected",
};

interface Props {
  status: ChatState["status"];
  onStop: () => void;
}

export function ChatHeader({ status, onStop }: Props) {
  return (
    <header className="chat-header">
      <span className="brand">LoopPlane</span>
      <span className="status" data-status={status}>
        <span className="dot" aria-hidden="true" />
        {LABEL[status]}
      </span>
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
