// @vitest-environment jsdom
import { initTheme, resolveTheme, storedTheme, toggleTheme } from "../theme/theme";

function mockMatchMedia(prefersDark: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: prefersDark && query.includes("dark"),
    media: query,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
  })) as unknown as typeof window.matchMedia;
}

describe("theme", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
  });

  it("resolves the stored theme when present", () => {
    localStorage.setItem("loopplane-theme", "dark");
    mockMatchMedia(false);
    expect(storedTheme()).toBe("dark");
    expect(resolveTheme()).toBe("dark");
  });

  it("falls back to the system preference when unset", () => {
    mockMatchMedia(true);
    expect(storedTheme()).toBeNull();
    expect(resolveTheme()).toBe("dark");
  });

  it("persists and applies the new theme on toggle", () => {
    mockMatchMedia(false);
    const start = initTheme();
    expect(start).toBe("light");
    const next = toggleTheme(start);
    expect(next).toBe("dark");
    expect(localStorage.getItem("loopplane-theme")).toBe("dark");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
  });

  it("falls back to light without throwing when matchMedia is unavailable", () => {
    window.matchMedia = (() => {
      throw new Error("blocked");
    }) as unknown as typeof window.matchMedia;
    expect(() => resolveTheme()).not.toThrow();
    expect(resolveTheme()).toBe("light");
  });
});
