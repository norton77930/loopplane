import { type ReactNode } from "react";
import {
  PresentationI18nProvider,
  useTranslation as useSharedTranslation,
} from "@loopplane/cowork-presentation";

import { en, zhTW, type Locale } from "./strings";

const MAPS: Record<Locale, Record<string, string>> = { en, "zh-TW": zhTW };
const KEY = "loopplane-locale";

/** Web adapter keeps its persisted locale key and existing public lookup behavior. */
export function t(key: string, locale: Locale): string {
  return MAPS[locale]?.[key] ?? en[key] ?? key;
}

export function I18nProvider({ children }: { children: ReactNode }) {
  return <PresentationI18nProvider messages={MAPS} storageKey={KEY}>{children}</PresentationI18nProvider>;
}

export interface WebTranslation {
  t: (key: string) => string;
  locale: Locale;
  setLocale: (locale: Locale) => void;
}

export function useTranslation(): WebTranslation {
  const shared = useSharedTranslation();
  const locale = shared.locale as Locale;
  return {
    locale,
    t: (key) => {
      const value = shared.t(key);
      return value === key ? t(key, locale) : value;
    },
    setLocale: shared.setLocale as (locale: Locale) => void,
  };
}
