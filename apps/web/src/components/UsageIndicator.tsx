import type { TokenUsage } from "../api/types";
import type { UsageState } from "../state/chat";

// A compact token-usage indicator (FR-006/007): the last turn + the session total. Hidden when
// the session total is all-zero (a stub/demo provider or a turn with no usage shows nothing —
// FR-008); cached/reasoning sub-counts show only when non-zero.
function isZero(usage: TokenUsage): boolean {
  return (
    usage.input_tokens === 0 &&
    usage.output_tokens === 0 &&
    usage.cached_tokens === 0 &&
    usage.reasoning_tokens === 0
  );
}

export function UsageIndicator({ usage }: { usage: UsageState }) {
  if (isZero(usage.total)) return null;
  const { last, total } = usage;

  return (
    <span className="usage" data-testid="usage">
      {last && !isZero(last) && (
        <span className="usage-turn">
          turn {last.input_tokens} in / {last.output_tokens} out
        </span>
      )}
      <span className="usage-total">
        session {total.input_tokens} in / {total.output_tokens} out
        {total.cached_tokens > 0 ? ` / ${total.cached_tokens} cached` : ""}
        {total.reasoning_tokens > 0 ? ` / ${total.reasoning_tokens} reasoning` : ""}
      </span>
    </span>
  );
}
