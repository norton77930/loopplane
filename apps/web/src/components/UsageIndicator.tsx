import type { TokenUsage } from "../api/types";
import type { UsageState } from "../state/chat";

// A compact token-usage indicator (026) + an optional client-side cost estimate (029). Hidden when
// the session total is all-zero; cached/reasoning sub-counts show only when non-zero; the cost
// (when provided) is clearly labeled an estimate.
function isZero(usage: TokenUsage): boolean {
  return (
    usage.input_tokens === 0 &&
    usage.output_tokens === 0 &&
    usage.cached_tokens === 0 &&
    usage.reasoning_tokens === 0
  );
}

interface Props {
  usage: UsageState;
  cost?: number | null;
}

export function UsageIndicator({ usage, cost }: Props) {
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
      {cost != null && <span className="usage-cost">~${cost.toFixed(4)} (est.)</span>}
    </span>
  );
}
