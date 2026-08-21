import { describe, expect, it } from "vitest";

import {
  COMPOSER_MAX_HEIGHT,
  growTextarea,
  resetTextareaHeight,
  shouldSubmitOnKey,
} from "../composer";

function fakeTextarea(scrollHeight: number): HTMLTextAreaElement {
  return {
    style: {} as Record<string, string>,
    get scrollHeight() {
      return scrollHeight;
    },
  } as unknown as HTMLTextAreaElement;
}

describe("growTextarea", () => {
  it("matches the content height", () => {
    const el = fakeTextarea(84);

    growTextarea(el);

    expect(el.style.height).toBe("84px");
  });

  it("stops growing at the cap so the message list keeps its room", () => {
    const el = fakeTextarea(4000);

    growTextarea(el);

    expect(el.style.height).toBe(`${COMPOSER_MAX_HEIGHT}px`);
  });

  it("tolerates a missing element", () => {
    expect(() => growTextarea(null)).not.toThrow();
    expect(() => resetTextareaHeight(null)).not.toThrow();
  });
});

describe("shouldSubmitOnKey", () => {
  it("sends on a plain Enter", () => {
    expect(shouldSubmitOnKey({ key: "Enter", shiftKey: false })).toBe(true);
  });

  it("does not send on Shift+Enter", () => {
    expect(shouldSubmitOnKey({ key: "Enter", shiftKey: true })).toBe(false);
  });

  it("ignores other keys", () => {
    expect(shouldSubmitOnKey({ key: "a", shiftKey: false })).toBe(false);
  });

  it("does not send while an IME is composing", () => {
    // Typing Chinese and pressing Enter accepts a candidate. Sending there would
    // fire off a half-finished word.
    expect(
      shouldSubmitOnKey({
        key: "Enter",
        shiftKey: false,
        nativeEvent: { isComposing: true },
      }),
    ).toBe(false);
  });

  it("also honours the keyCode 229 IME signal", () => {
    expect(
      shouldSubmitOnKey({
        key: "Enter",
        shiftKey: false,
        nativeEvent: { keyCode: 229 },
      }),
    ).toBe(false);
  });

  it("sends once composition has ended", () => {
    expect(
      shouldSubmitOnKey({
        key: "Enter",
        shiftKey: false,
        nativeEvent: { isComposing: false, keyCode: 13 },
      }),
    ).toBe(true);
  });
});
