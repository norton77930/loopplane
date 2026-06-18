import { estimateCost } from "../pricing";

const usage = (input: number, output: number) => ({
  input_tokens: input,
  output_tokens: output,
  cached_tokens: 0,
  reasoning_tokens: 0,
});

describe("estimateCost", () => {
  it("computes a cost from usage and the bundled price table", () => {
    // 1M input * $3/1M + 1M output * $15/1M = $18
    expect(estimateCost(usage(1_000_000, 1_000_000), "claude-sonnet")).toBeCloseTo(18);
  });

  it("returns null for an unknown or absent model (graceful)", () => {
    expect(estimateCost(usage(100, 100), "no-such-model")).toBeNull();
    expect(estimateCost(usage(100, 100), null)).toBeNull();
  });
});
