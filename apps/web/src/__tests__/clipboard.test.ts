// @vitest-environment jsdom
import { copyText } from "../lib/clipboard";

function setClipboard(value: unknown) {
  Object.defineProperty(navigator, "clipboard", {
    value,
    configurable: true,
    writable: true,
  });
}

describe("copyText", () => {
  it("uses the async clipboard API when available", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    setClipboard({ writeText });
    await expect(copyText("hello")).resolves.toBe(true);
    expect(writeText).toHaveBeenCalledWith("hello");
  });

  it("falls back to execCommand when the async API is unavailable", async () => {
    setClipboard(undefined);
    const exec = vi.fn().mockReturnValue(true);
    Object.defineProperty(document, "execCommand", {
      value: exec,
      configurable: true,
      writable: true,
    });
    await expect(copyText("hi")).resolves.toBe(true);
    expect(exec).toHaveBeenCalledWith("copy");
  });
});
