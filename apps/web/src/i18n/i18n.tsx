import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { en, zhTW, type Locale } from "./strings";

// A tiny in-house i18n (unit 029): a per-locale string lookup with an English fallback, a provider
// that persists the choice, and a hook. Outside a provider the hook defaults to English (so an
// isolated component test renders the default strings without wrapping).
const MAPS: Record<Locale, Record<string, string>> = { en, "zh-TW": zhTW };
const KEY = "loopplane-locale";

/** Lookup with an English fallback, then the key itself — never a blank (FR-003). */
export function t(key: string, locale: Locale): string {
  return MAPS[locale]?.[key] ?? en[key] ?? key;
}

function storedLocale(): Locale {
  try {
    const value = localStorage.getItem(KEY);
    return value === "en" || value === "zh-TW" ? value : "en";
  } catch {
    return "en";
  }
}

interface Translation {
  t: (key: string) => string;
  locale: Locale;
  setLocale: (locale: Locale) => void;
}

const I18nContext = createContext<Translation | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(() => storedLocale());
  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  function setLocale(next: Locale) {
    setLocaleState(next);
    try {
      localStorage.setItem(KEY, next);
    } catch {
      // storage blocked — keep the in-memory choice without throwing
    }
  }
  const value: Translation = { t: (key) => t(key, locale), locale, setLocale };
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useTranslation(): Translation {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    return { t: (key) => t(key, "en"), locale: "en", setLocale: () => undefined };
  }
  return ctx;
}
