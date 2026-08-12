import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CapabilitySettingsView } from "../components/CapabilitySettingsView";
import { InspectionPanel } from "../components/InspectionPanel";
import { InspectionSidebar } from "../components/InspectionSidebar";

describe("InspectionSidebar host projections", () => {
  it("renders host-owned unpriced and unavailable inspection posture without private detail", () => {
    render(
      <InspectionSidebar
        inspection={{
          sessionId: "session-1",
          skills: [],
          tools: [],
          mcp: [],
          memory: [],
          unavailable: false,
          cost: { status: "unpriced" },
          context: { status: "unavailable" },
          uploads: { status: "unavailable" },
          artifacts: { status: "read_only" },
        }}
        capabilities={[]}
        agentControls={{
          sessionId: "session-1",
          defaultMode: null,
          selectableModes: [],
          activeRun: null,
          lastAcceptedRun: { mode: "plan", state: "settled", planActive: false },
          budget: {
            tracking: "unavailable",
            pricing: "unpriced",
            sessionGuard: "unknown",
            monthlyGuard: "unknown",
          },
          actions: [],
          unavailable: false,
        }}
      />,
    );

    expect(screen.getAllByText("Unpriced")).toHaveLength(2);
    expect(screen.getAllByText("Unavailable")).toHaveLength(2);
    expect(screen.getByText("Read only")).toBeInTheDocument();
    expect(screen.getByText("plan")).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/secret|C:\\Users|private-rule/i);
  });

  it("uses the same honest labels for priced and available host inspection status", () => {
    const inspection = {
      sessionId: "session-1",
      skills: [], tools: [], mcp: [], memory: [], unavailable: false,
      cost: { status: "priced" as const },
      context: { status: "available" as const },
      uploads: { status: "unknown" as const },
      artifacts: { status: "read_only" as const },
    };
    render(<><InspectionPanel inspection={inspection} /><InspectionSidebar inspection={inspection} capabilities={[]} /></>);

    expect(screen.getAllByText("Priced")).toHaveLength(2);
    expect(screen.getAllByText("Available")).toHaveLength(2);
    expect(screen.getAllByText("Unknown")).toHaveLength(2);
    expect(screen.getAllByText("Read only")).toHaveLength(2);
  });

  it("marks absent capability projections unavailable instead of rendering an empty success state", () => {
    render(
      <CapabilitySettingsView
        title="Capability settings"
        categoriesLabel="Settings categories"
        backLabel="Back"
        tabs={[{ id: "capabilities", label: "Capabilities" }]}
        capabilities={null}
        renderTab={() => <p>Host-owned settings only.</p>}
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent("Capability status unavailable.");
  });
});
