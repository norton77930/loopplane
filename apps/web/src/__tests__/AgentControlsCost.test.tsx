import { render, screen, within } from "@testing-library/react";

import type {
  AgentControlProjection,
  MonthlyCostView,
  SessionCostView,
} from "../api/types";
import { AgentControlsSettings } from "../components/settings/AgentControlsSettings";

function projection(
  pricing: AgentControlProjection["budget"]["pricing"],
): AgentControlProjection {
  return {
    session_id: "s1",
    permission: {
      default_mode: null,
      selectable_modes: [],
      selection_scope: "run",
      rules_configured: false,
      rule_default: "ask",
      rule_decisions: ["deny", "ask", "allow"],
      plan_entry_available: false,
      plan_exit_requires_approval: true,
      active_run: null,
      last_accepted_run: null,
    },
    budget: {
      tracking: "available",
      pricing,
      message_guard: "enabled",
      session_guard: "within",
      monthly_guard: "near",
      pre_turn_guard: "enabled",
    },
    actions: [],
  };
}

function renderCost(
  current: AgentControlProjection,
  sessionCost: SessionCostView | null,
  monthlyCost: MonthlyCostView | null,
  costFailed = false,
) {
  render(
    <AgentControlsSettings
      projection={current}
      loading={false}
      failed={false}
      permissionModeDraft={null}
      onPermissionModeChange={() => undefined}
      onRefresh={() => undefined}
      sessionCost={sessionCost}
      monthlyCost={monthlyCost}
      costLoading={false}
      costFailed={costFailed}
    />,
  );
}

describe("AgentControlsSettings cost", () => {
  it("shows exact authoritative zero separately from monthly nonzero spend", () => {
    renderCost(
      projection("priced"),
      { session_id: "s1", usd_spent: "0" },
      { principal_id: "caller", month: "2026-07", usd_spent: "12.3400" },
    );

    const cost = within(screen.getByRole("region", { name: "Cost and budget" }));
    expect(cost.getByText("Session spend").nextSibling).toHaveTextContent("$0");
    expect(cost.getByText("Monthly spend").nextSibling).toHaveTextContent(
      "$12.3400",
    );
    expect(cost.getByText("Message guard").nextSibling).toHaveTextContent("enabled");
    expect(cost.getByText("Monthly guard").nextSibling).toHaveTextContent("near");
    expect(screen.queryByText("caller")).toBeNull();
  });

  it("labels partially priced exact totals without rounding", () => {
    renderCost(
      projection("partially_unpriced"),
      { session_id: "s1", usd_spent: "1.2300" },
      { principal_id: "caller", month: "2026-07", usd_spent: "2.3400" },
    );

    expect(screen.getByText("$1.2300 (partially priced)")).toBeInTheDocument();
    expect(screen.getByText("$2.3400 (partially priced)")).toBeInTheDocument();
  });

  it("never formats missing or unpriced cost as zero", () => {
    const { unmount } = render(
      <AgentControlsSettings
        projection={projection("unpriced")}
        loading={false}
        failed={false}
        permissionModeDraft={null}
        onPermissionModeChange={() => undefined}
        onRefresh={() => undefined}
        sessionCost={{ session_id: "s1", usd_spent: null }}
        monthlyCost={{ principal_id: "caller", month: "2026-07", usd_spent: null }}
        costLoading={false}
        costFailed={false}
      />,
    );
    expect(screen.getAllByText("Unpriced")).toHaveLength(2);
    expect(screen.queryByText("$0")).toBeNull();
    unmount();

    renderCost(projection("priced"), null, null, true);
    expect(screen.getAllByText("Unavailable")).toHaveLength(2);
    expect(screen.queryByText("$0")).toBeNull();
  });
});
