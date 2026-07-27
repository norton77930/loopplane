import type { TokenUsage } from "../api/types";
import type { UsageState } from "../state/chat";

// A compact token-usage indicator (026) plus optional authoritative server cost (064/077).
// Cached/reasoning sub-counts show only when non-zero. Exact decimal cost strings are rendered
// without client-side rounding; known zero remains visible even before token totals arrive.
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
  cost?: string | null;
}

export function UsageIndicator({ usage, cost }: Props) {
  const usageIsZero = isZero(usage.total);
  if (usageIsZero && cost == null) return null;
  const { last, total } = usage;

  return (
    <span className="usage" data-testid="usage">
      {!usageIsZero && last && !isZero(last) && (
        <span className="usage-turn">
          turn {last.input_tokens} in / {last.output_tokens} out
        </span>
      )}
      {!usageIsZero && (
        <span className="usage-total">
          session {total.input_tokens} in / {total.output_tokens} out
          {total.cached_tokens > 0 ? ` / ${total.cached_tokens} cached` : ""}
          {total.reasoning_tokens > 0 ? ` / ${total.reasoning_tokens} reasoning` : ""}
        </span>
      )}
      {cost != null && <span className="usage-cost">${cost}</span>}
    </span>
  );
}
