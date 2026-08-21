/**
 * Curated model catalog (083 W2-A, FR-003).
 *
 * Static data only: the catalog feeds a typing aid for the model field, never
 * a gate — free-form ids stay valid, so an id we could not verify is simply
 * not listed. Anthropic ids were checked against Anthropic's current model
 * documentation at authoring time (2026-08, alias forms without date
 * suffixes); the other providers list only the example ids this repo already
 * ships, because we have no equally authoritative source to curate more from.
 *
 * The configured id is marked `current` — and appended when the curated list
 * does not contain it — so the picker always shows what is active. Input is a
 * two-field projection of the vault view; key material never reaches this
 * module.
 */

export type ProviderCatalogModel = { id: string; current: boolean };

export type ProviderCatalogEntry = {
  provider: string;
  models: ProviderCatalogModel[];
};

const CURATED: readonly { provider: string; models: readonly string[] }[] = [
  {
    provider: "anthropic",
    models: [
      "claude-opus-5",
      "claude-sonnet-5",
      "claude-haiku-4-5",
      "claude-fable-5",
      "claude-opus-4-8",
      "claude-sonnet-4-6",
    ],
  },
  { provider: "openai", models: ["gpt-4o"] },
  { provider: "gemini", models: ["gemini-2.5-pro"] },
  { provider: "openrouter", models: ["anthropic/claude-sonnet-5"] },
  // Ollama serves whatever was pulled onto this machine; a static list would
  // only mislead, so the field stays free-form.
  { provider: "ollama", models: [] },
];

export function buildProviderCatalog(
  configured: { provider: string; modelId: string } | null,
): ProviderCatalogEntry[] {
  return CURATED.map(({ provider, models }) => {
    const active = configured !== null && configured.provider === provider;
    const listed: ProviderCatalogModel[] = models.map((id) => ({
      id,
      current: active && id === configured.modelId,
    }));
    if (active && !models.includes(configured.modelId)) {
      listed.push({ id: configured.modelId, current: true });
    }
    return { provider, models: listed };
  });
}
