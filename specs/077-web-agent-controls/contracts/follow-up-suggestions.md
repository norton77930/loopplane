# Contract: Deterministic Follow-Up Suggestions

## Inputs

Suggestion generation may inspect only state already available to the current Web view:

- whether the session is empty or a run has settled;
- public terminal reason categories such as `budget-exceeded`;
- current safe workspace-context label/status;
- completed/failed attachment names and statuses;
- public tool outcome/reference metadata already displayed;
- active locale and whether the composer is available.

It must not inspect private configuration, fetch remote state, read resource content, or infer an authorization result.

## Output

- Zero to three localized suggestions.
- Each suggestion has a deterministic id, editable text, reason category, and stable ordering.
- Suggestions are visually and semantically identified as optional user-input proposals, not assistant output.

## Interaction

- Selecting a suggestion populates the composer; it does not submit.
- The user may edit, dismiss, or ignore it.
- Sending uses the ordinary authenticated session submission path and any selected per-run mode/upload references.
- Suggestions are removed/rederived when session, locale, permission selection, context, attachment state, or terminal outcome changes.

## Prohibited effects

Suggestion derivation and selection perform:

- zero model calls;
- zero tool calls;
- zero network requests;
- zero automatic turns;
- zero hidden cost;
- zero approval or permission decisions.

## Accessibility and localization

- Suggestions are keyboard reachable, dismissible, and do not steal focus from pending approval/question dialogs.
- The suggestion group has a localized accessible name.
- Selection moves or keeps focus in the editable composer according to the existing composer pattern.
- English and Traditional Chinese strings are complete; document language continues to follow the selected locale.
