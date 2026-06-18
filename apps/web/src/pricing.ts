import type { TokenUsage } from "./api/types";

// A client-side cost estimate (unit 029): the unit-026 token usage times a bundled price table.
// These are generic, public example prices (USD per 1,000,000 tokens) keyed by the catalog model
// id an operator configures (unit 028). The result is an ESTIMATE only — authoritative server-side
// pricing is deferred (out of scope). No price entry -> null (the UI then shows counts only).

export interface ModelPrice {
  input: number;
  output: number;
}

export const PRICE_TABLE: Record<string, ModelPrice> = {
  "claude-opus": { input: 15, output: 75 },
  "claude-sonnet": { input: 3, output: 15 },
  "claude-haiku": { input: 0.8, output: 4 },
  "gpt-4o": { input: 2.5, output: 10 },
  "gpt-4o-mini": { input: 0.15, output: 0.6 },
};

export function estimateCost(usage: TokenUsage, model: string | null): number | null {
  if (!model) return null;
  const price = PRICE_TABLE[model];
  if (!price) return null;
  return (usage.input_tokens * price.input + usage.output_tokens * price.output) / 1_000_000;
}
