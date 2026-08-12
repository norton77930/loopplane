// @ts-expect-error Vitest provides Node built-ins at runtime; the Web tsconfig intentionally omits Node types.
import { readFileSync } from "node:fs";

const styles = readFileSync(
  new URL("../../../../packages/cowork-presentation/src/styles.css", import.meta.url),
  "utf8",
);

describe("accessibility style contracts", () => {
  it("preserves focus, reflow, reduced motion, and forced-color visibility", () => {
    expect(styles).not.toMatch(/input:focus\s*{[^}]*outline:\s*none/);
    expect(styles).not.toMatch(/textarea:focus\s*{[^}]*outline:\s*none/);
    expect(styles).toContain("overflow-x: clip");
    expect(styles).toContain("@media (prefers-reduced-motion: reduce)");
    expect(styles).toContain("@media (forced-colors: active)");
  });
});
