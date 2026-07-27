import {
  deriveFollowUpSuggestions,
  followUpSuggestionStaleKey,
} from "../followUpSuggestions";

describe("deriveFollowUpSuggestions", () => {
  it("uses stable priority ordering and caps output at three", () => {
    const suggestions = deriveFollowUpSuggestions({
      locale: "en",
      composerAvailable: true,
      empty: false,
      settled: true,
      terminalReason: "budget-exceeded",
      contextLabel: "Workspace",
      attachments: [{ name: "broken.txt", status: "error" }],
      tools: [{ outcome: "success", artifactReference: "artifact://report" }],
    });

    expect(suggestions.map((item) => item.id)).toEqual([
      "review-budget",
      "retry-attachment",
      "use-artifact",
    ]);
  });

  it("returns no proposals when the composer is unavailable", () => {
    expect(
      deriveFollowUpSuggestions({
        locale: "en",
        composerAvailable: false,
        empty: true,
        settled: false,
        attachments: [],
        tools: [],
      }),
    ).toEqual([]);
  });

  it("changes its stale key when locale, session, posture, context, or attachments change", () => {
    const base = {
      locale: "en" as const,
      sessionKey: "s1",
      permissionMode: "plan",
      composerAvailable: true,
      empty: false,
      settled: true,
      contextLabel: "Workspace",
      attachments: [{ name: "notes.txt", status: "done" as const }],
      tools: [],
    };

    expect(followUpSuggestionStaleKey(base)).not.toBe(
      followUpSuggestionStaleKey({ ...base, locale: "zh-TW" }),
    );
    expect(followUpSuggestionStaleKey(base)).not.toBe(
      followUpSuggestionStaleKey({ ...base, sessionKey: "s2" }),
    );
    expect(followUpSuggestionStaleKey(base)).not.toBe(
      followUpSuggestionStaleKey({ ...base, permissionMode: "dontAsk" }),
    );
    expect(followUpSuggestionStaleKey(base)).not.toBe(
      followUpSuggestionStaleKey({ ...base, contextLabel: "Other" }),
    );
    expect(followUpSuggestionStaleKey(base)).not.toBe(
      followUpSuggestionStaleKey({ ...base, attachments: [] }),
    );
  });
});
