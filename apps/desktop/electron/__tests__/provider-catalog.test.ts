import { describe, expect, it } from "vitest";

import {
  buildProviderCatalog,
  type ProviderCatalogEntry,
} from "../provider-catalog";

function entryFor(
  entries: readonly ProviderCatalogEntry[],
  provider: string,
): ProviderCatalogEntry {
  const found = entries.find((entry) => entry.provider === provider);
  if (!found) throw new Error(`no catalog entry for ${provider}`);
  return found;
}

describe("provider catalog (083 W2-A)", () => {
  it("lists curated models per provider and marks only the configured id current", () => {
    const entries = buildProviderCatalog({
      provider: "anthropic",
      modelId: "claude-opus-5",
    });

    const anthropic = entryFor(entries, "anthropic");
    expect(anthropic.models.map((m) => m.id)).toContain("claude-opus-5");
    expect(anthropic.models.filter((m) => m.current).map((m) => m.id)).toEqual([
      "claude-opus-5",
    ]);

    // Every other provider still lists its curated ids, with nothing current.
    const openai = entryFor(entries, "openai");
    expect(openai.models.length).toBeGreaterThan(0);
    expect(openai.models.every((m) => !m.current)).toBe(true);
  });

  it("appends a configured id that the curated list does not contain", () => {
    const entries = buildProviderCatalog({
      provider: "anthropic",
      modelId: "claude-experimental-nightly",
    });

    const anthropic = entryFor(entries, "anthropic");
    const current = anthropic.models.filter((m) => m.current);
    expect(current).toEqual([{ id: "claude-experimental-nightly", current: true }]);
    // Appended, not replacing the curated ids.
    expect(anthropic.models.map((m) => m.id)).toContain("claude-opus-5");
  });

  it("marks nothing current when no provider is configured", () => {
    const entries = buildProviderCatalog(null);

    expect(entries.length).toBeGreaterThan(0);
    for (const entry of entries) {
      expect(entry.models.every((m) => !m.current)).toBe(true);
    }
  });

  it("has no entry for an unknown provider and carries no key material", () => {
    const entries = buildProviderCatalog({
      provider: "weird-provider",
      modelId: "sk-ant-api03-secret4f2a",
    });

    // An unknown provider gains no catalog entry of its own...
    expect(entries.some((e) => e.provider === "weird-provider")).toBe(false);
    // ...and its configured id is not spliced into someone else's list.
    const serialized = JSON.stringify(entries);
    expect(serialized).not.toContain("sk-ant-api03");
    expect(serialized).not.toContain("hasKey");
    expect(serialized).not.toContain("keyHint");
  });

  it("keeps the local runtime free-form: ollama lists no static ids", () => {
    const entries = buildProviderCatalog(null);
    expect(entryFor(entries, "ollama").models).toEqual([]);
  });
});
