// Re-exported from the shared presentation package so Web and Desktop resolve
// the same stored preference and the same `data-theme` attribute.
export {
  applyTheme,
  initTheme,
  persistTheme,
  resolveTheme,
  storedTheme,
  systemTheme,
  toggleTheme,
  type StoredTheme,
  type Theme,
} from "@loopplane/cowork-presentation";
