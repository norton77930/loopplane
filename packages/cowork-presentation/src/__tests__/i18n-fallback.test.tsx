import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ApprovalDialog } from "../components/ApprovalDialog";
import { PresentationI18nProvider } from "../i18n/i18n";

describe("shared vocabulary fallback", () => {
  it("reaches a host that supplies its own messages", () => {
    // A host passing `messages` replaces the default map entirely. Without the
    // vocabulary as a last layer this rendered the raw keys — "approval.allow",
    // "tool.run_command" — to every host that had not copied them in.
    render(
      <PresentationI18nProvider messages={{ en: { "some.other.key": "x" } }}>
        <ApprovalDialog toolName="run_command" onDecide={() => undefined} />
      </PresentationI18nProvider>,
    );

    expect(screen.getByText("Allow")).toBeInTheDocument();
    expect(screen.getByText("Always allow this session")).toBeInTheDocument();
    expect(
      screen.getByText(/runs a command on this computer/i),
    ).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/approval\.|tool\./);
  });

  it("lets a host override the shared wording for its own locale", () => {
    render(
      <PresentationI18nProvider
        messages={{ en: { "approval.allow": "Permit" } }}
      >
        <ApprovalDialog toolName="read_file" onDecide={() => undefined} />
      </PresentationI18nProvider>,
    );

    expect(screen.getByText("Permit")).toBeInTheDocument();
    expect(screen.queryByText("Allow")).not.toBeInTheDocument();
  });
});
