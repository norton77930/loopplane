/**
 * Keyboard focus helpers (078 T055 scaffold).
 *
 * Full high-zoom / forced-colors / reduced-motion styling is gated on T050 RED
 * Chromium inventory; this module only exports deterministic focus utilities.
 */

export type Focusable = HTMLElement;

export function focusElement(el: Focusable | null | undefined): void {
  if (!el) return;
  try {
    el.focus({ preventScroll: false });
  } catch {
    el.focus();
  }
}

/** Restore focus to a prior element or a documented fallback. */
export function restoreFocus(
  previous: Focusable | null | undefined,
  fallback: Focusable | null | undefined,
): void {
  if (previous && document.contains(previous)) {
    focusElement(previous);
    return;
  }
  focusElement(fallback);
}

/** Dismiss an overlay only for Escape, then return focus to its stable opener. */
export function dismissOnEscape(
  event: Pick<KeyboardEvent, "key" | "preventDefault">,
  onDismiss: () => void,
  previous: Focusable | null | undefined,
  fallback: Focusable | null | undefined,
): boolean {
  if (event.key !== "Escape") return false;
  event.preventDefault();
  onDismiss();
  restoreFocus(previous, fallback);
  return true;
}

export const REDUCED_MOTION_MEDIA = "(prefers-reduced-motion: reduce)";

export function prefersReducedMotion(
  matchMedia: (query: string) => { matches: boolean } = window.matchMedia.bind(
    window,
  ),
): boolean {
  try {
    return matchMedia(REDUCED_MOTION_MEDIA).matches;
  } catch {
    return false;
  }
}
