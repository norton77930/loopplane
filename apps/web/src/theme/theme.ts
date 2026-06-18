// Theme preference (FR-013): a light/dark choice persisted in localStorage, defaulting to the
// OS preference when unset. All storage / matchMedia access is wrapped so a blocked or
// unavailable store falls back to light without throwing (data-model.md; edge case).

export type Theme = "light" | "dark";
export type StoredTheme = Theme | null;

const KEY = "loopplane-theme";

export function storedTheme(): StoredTheme {
  try {
    const value = localStorage.getItem(KEY);
    return value === "light" || value === "dark" ? value : null;
  } catch {
    return null;
  }
}

export function systemTheme(): Theme {
  try {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  } catch {
    return "light";
  }
}

export function resolveTheme(): Theme {
  return storedTheme() ?? systemTheme();
}

export function applyTheme(theme: Theme): void {
  try {
    document.documentElement.setAttribute("data-theme", theme);
  } catch {
    // No document (e.g. a non-DOM environment) — nothing to apply.
  }
}

export function persistTheme(theme: Theme): void {
  try {
    localStorage.setItem(KEY, theme);
  } catch {
    // Storage blocked — keep the in-memory choice without throwing.
  }
}

/** Resolve the initial theme and apply it. Returns the resolved theme. */
export function initTheme(): Theme {
  const theme = resolveTheme();
  applyTheme(theme);
  return theme;
}

/** Flip, persist, and apply; returns the new theme. */
export function toggleTheme(current: Theme): Theme {
  const next: Theme = current === "dark" ? "light" : "dark";
  persistTheme(next);
  applyTheme(next);
  return next;
}
