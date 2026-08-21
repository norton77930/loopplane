/**
 * Shared metadata-safe audit presentation RED contract (078 T072).
 */

import { createElement, type ComponentType } from "react";
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import * as presentation from "../index";

type AuditEntry = {
  audit_id: string;
  session_id: string;
  turn_ordinal: number;
  checkpoint_sequence: number;
  recorded_at: string | null;
  state: "completed" | "interrupted";
  termination_reason: string | null;
  turns_taken: number | null;
};

type AuditViewProps = {
  entries: AuditEntry[];
  loading?: boolean;
  failed?: boolean;
};

describe("AuditView", () => {
  it("renders only allowlisted logical-turn metadata", () => {
    const AuditView = Reflect.get(presentation, "AuditView") as
      ComponentType<AuditViewProps> | undefined;
    expect(AuditView).toBeTypeOf("function");

    const entries = [
      {
        audit_id: "audit-one",
        session_id: "session-one",
        turn_ordinal: 1,
        checkpoint_sequence: 7,
        recorded_at: "2026-08-10T00:00:00Z",
        state: "completed" as const,
        termination_reason: "natural-completion",
        turns_taken: 2,
        prompt: "PRIVATE PROMPT MUST NOT RENDER",
        model_output: "PRIVATE MODEL OUTPUT MUST NOT RENDER",
        tool_output: "PRIVATE TOOL OUTPUT MUST NOT RENDER",
        private_path: "X:\\private\\workspace",
      },
      {
        audit_id: "audit-two",
        session_id: "session-one",
        turn_ordinal: 2,
        checkpoint_sequence: 12,
        recorded_at: null,
        state: "interrupted" as const,
        termination_reason: null,
        turns_taken: null,
      },
    ] as AuditEntry[];

    render(createElement(AuditView!, { entries }));

    const region = screen.getByRole("region", { name: "Turn audit" });
    const rows = within(region).getAllByRole("listitem");
    expect(rows).toHaveLength(2);
    expect(within(rows[0]!).getByText(/completed/i)).toBeInTheDocument();
    expect(
      within(rows[0]!).getByText(/natural-completion/i),
    ).toBeInTheDocument();
    expect(within(rows[0]!).getByText(/2 turns?/i)).toBeInTheDocument();
    expect(within(rows[1]!).getByText(/interrupted/i)).toBeInTheDocument();

    expect(region).not.toHaveTextContent("PRIVATE PROMPT MUST NOT RENDER");
    expect(region).not.toHaveTextContent(
      "PRIVATE MODEL OUTPUT MUST NOT RENDER",
    );
    expect(region).not.toHaveTextContent("PRIVATE TOOL OUTPUT MUST NOT RENDER");
    expect(region).not.toHaveTextContent("X:\\private\\workspace");
  });

  it("shows honest loading, empty, and unavailable states", () => {
    const AuditView = Reflect.get(presentation, "AuditView") as
      ComponentType<AuditViewProps> | undefined;
    expect(AuditView).toBeTypeOf("function");

    const { rerender } = render(
      createElement(AuditView!, { entries: [], loading: true }),
    );
    expect(screen.getByRole("status")).toHaveTextContent(/loading/i);

    rerender(createElement(AuditView!, { entries: [] }));
    expect(screen.getByText(/no audit entries/i)).toBeInTheDocument();

    rerender(createElement(AuditView!, { entries: [], failed: true }));
    expect(screen.getByRole("alert")).toHaveTextContent(/unavailable/i);
  });
});
