import type { Locale } from "./i18n/strings";

export type FollowUpSuggestionReason =
  | "budget"
  | "attachment"
  | "artifact"
  | "context"
  | "settled"
  | "empty";

export interface FollowUpSuggestionDefinition {
  id: string;
  reason: FollowUpSuggestionReason;
  textKey: string;
}

export interface FollowUpSuggestionInput {
  locale: Locale;
  sessionKey?: string | null;
  permissionMode?: string | null;
  composerAvailable: boolean;
  empty: boolean;
  settled: boolean;
  terminalReason?: string | null;
  contextLabel?: string | null;
  attachments: Array<{ name: string; status: "uploading" | "done" | "error" }>;
  tools: Array<{
    outcome?: "success" | "failure";
    artifactReference?: string;
  }>;
}

const MAX_SUGGESTIONS = 3;

export function deriveFollowUpSuggestions(
  input: FollowUpSuggestionInput,
): FollowUpSuggestionDefinition[] {
  if (!input.composerAvailable) return [];

  const suggestions: FollowUpSuggestionDefinition[] = [];
  if (input.terminalReason === "budget-exceeded") {
    suggestions.push({
      id: "review-budget",
      reason: "budget",
      textKey: "suggestions.reviewBudget",
    });
  }
  if (input.attachments.some((attachment) => attachment.status === "error")) {
    suggestions.push({
      id: "retry-attachment",
      reason: "attachment",
      textKey: "suggestions.retryAttachment",
    });
  }
  if (input.tools.some((tool) => Boolean(tool.artifactReference))) {
    suggestions.push({
      id: "use-artifact",
      reason: "artifact",
      textKey: "suggestions.useArtifact",
    });
  }
  if (input.contextLabel) {
    suggestions.push({
      id: "inspect-context",
      reason: "context",
      textKey: "suggestions.inspectContext",
    });
  }
  if (input.settled) {
    suggestions.push({
      id: "continue-after-run",
      reason: "settled",
      textKey: "suggestions.continue",
    });
  }
  if (input.empty) {
    suggestions.push({
      id: "start-conversation",
      reason: "empty",
      textKey: "suggestions.start",
    });
  }
  return suggestions.slice(0, MAX_SUGGESTIONS);
}

export function followUpSuggestionStaleKey(input: FollowUpSuggestionInput): string {
  return JSON.stringify({
    locale: input.locale,
    sessionKey: input.sessionKey ?? null,
    permissionMode: input.permissionMode ?? null,
    composerAvailable: input.composerAvailable,
    empty: input.empty,
    settled: input.settled,
    terminalReason: input.terminalReason ?? null,
    contextLabel: input.contextLabel ?? null,
    attachments: input.attachments.map(({ name, status }) => ({ name, status })),
    tools: input.tools.map(({ outcome, artifactReference }) => ({
      outcome: outcome ?? null,
      artifactReference: artifactReference ?? null,
    })),
  });
}
