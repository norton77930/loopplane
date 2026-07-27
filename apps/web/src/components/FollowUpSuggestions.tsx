import type { FollowUpSuggestionReason } from "../followUpSuggestions";
import { useTranslation } from "../i18n/i18n";

export interface FollowUpSuggestionView {
  id: string;
  reason: FollowUpSuggestionReason;
  text: string;
}

export function FollowUpSuggestions({
  suggestions,
  onSelect,
  onDismiss,
}: {
  suggestions: FollowUpSuggestionView[];
  onSelect: (suggestion: FollowUpSuggestionView) => void;
  onDismiss: (id: string) => void;
}) {
  const { t } = useTranslation();
  if (suggestions.length === 0) return null;

  return (
    <section
      className="follow-up-suggestions"
      aria-label={t("suggestions.label")}
    >
      <div className="follow-up-heading">{t("suggestions.optionalInput")}</div>
      <div className="follow-up-list">
        {suggestions.map((suggestion) => (
          <div className="follow-up-item" key={suggestion.id}>
            <button
              type="button"
              className="follow-up-select"
              onClick={() => onSelect(suggestion)}
            >
              {suggestion.text}
            </button>
            <button
              type="button"
              className="follow-up-dismiss"
              aria-label={t("suggestions.dismiss")}
              onClick={() => onDismiss(suggestion.id)}
            >
              &times;
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}
