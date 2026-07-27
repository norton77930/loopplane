import { useTranslation } from "../i18n/i18n";
import { LOCALES, type Locale } from "../i18n/strings";

// The UI language switcher (029, FR-001): lists the available locales and changes the active one
// (persisted by the provider).
export function LanguageSwitcher() {
  const { t, locale, setLocale } = useTranslation();
  return (
    <select
      className="lang-switcher"
      aria-label={t("language.label")}
      value={locale}
      onChange={(event) => setLocale(event.target.value as Locale)}
    >
      {LOCALES.map((entry) => (
        <option key={entry.id} value={entry.id}>
          {entry.label}
        </option>
      ))}
    </select>
  );
}
