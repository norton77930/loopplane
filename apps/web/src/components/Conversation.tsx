import type { Turn } from "../state/chat";

export function Conversation({ turns }: { turns: Turn[] }) {
  return (
    <div className="conversation" data-testid="conversation">
      {turns.map((turn, index) => (
        <div key={index} className={`turn turn-${turn.role}`}>
          <span className="role">{turn.role}</span>
          <span className="text">{turn.text}</span>
        </div>
      ))}
    </div>
  );
}
