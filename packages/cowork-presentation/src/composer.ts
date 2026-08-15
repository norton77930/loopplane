/**
 * Composer keyboard and sizing behaviour, shared by Web and Desktop.
 *
 * The markup stays per-app — Desktop's prompt and submit control carry fixed
 * accessible names that the packaged UI-Automation smoke locates by, and Web's
 * composer hosts a command palette, a model selector and attachments — but the
 * two rules that are easy to get subtly wrong live here.
 */

/** Tallest a growing composer gets before it scrolls internally. */
export const COMPOSER_MAX_HEIGHT = 200;

/** Resize a textarea to its content, up to `maxHeight`. */
export function growTextarea(
  element: HTMLTextAreaElement | null,
  maxHeight: number = COMPOSER_MAX_HEIGHT,
): void {
  if (!element) return;
  // Collapse first: scrollHeight only shrinks once the element stops claiming
  // the taller size it already has.
  element.style.height = "auto";
  element.style.height = `${Math.min(element.scrollHeight, maxHeight)}px`;
}

/** Reset a textarea to a single row, e.g. after sending. */
export function resetTextareaHeight(element: HTMLTextAreaElement | null): void {
  if (!element) return;
  element.style.height = "auto";
}

/**
 * Whether a keydown should send the message.
 *
 * Enter sends and Shift+Enter inserts a newline — except while an input method
 * editor is composing. Typing Chinese, Japanese or Korean uses Enter to accept a
 * candidate, so a composer that ignores `isComposing` sends a half-finished word
 * the moment the user picks one. Browsers also report `keyCode === 229` for a
 * key routed to an IME, which is the fallback for engines that do not set
 * `isComposing` on the event itself.
 */
export function shouldSubmitOnKey(event: {
  key: string;
  shiftKey: boolean;
  nativeEvent?: { isComposing?: boolean; keyCode?: number } | null;
}): boolean {
  if (event.key !== "Enter" || event.shiftKey) return false;
  const native = event.nativeEvent;
  if (native?.isComposing) return false;
  if (native?.keyCode === 229) return false;
  return true;
}
