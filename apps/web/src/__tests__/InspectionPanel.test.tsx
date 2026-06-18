import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import type { ApiClient } from "../api/client";
import { InspectionPanel } from "../components/InspectionPanel";

function stubClient(overrides: Record<string, unknown> = {}): ApiClient {
  return {
    inspectSkills: async () => ({
      skills: [
        { name: "writer", description: "writes things", autonomous: true, approval_required: false, source: "skills" },
      ],
      problems: [],
    }),
    inspectTools: async () => [
      { name: "echo", description: "echoes", read_only: true, source: "internal" },
    ],
    inspectMcp: async () => [],
    inspectMemory: async () => [
      { type: "user", name: "pref", description: "a preference", snippet: "likes tabs" },
    ],
    ...overrides,
  } as unknown as ApiClient;
}

describe("InspectionPanel", () => {
  it("shows skills on open and switches to tools", async () => {
    render(<InspectionPanel client={stubClient()} />);
    expect(await screen.findByText("writer")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "Tools" }));
    expect(await screen.findByText("echo")).toBeInTheDocument();
  });

  it("shows a clear empty state for MCP with no servers", async () => {
    render(<InspectionPanel client={stubClient()} />);
    fireEvent.click(screen.getByRole("tab", { name: "MCP" }));
    expect(await screen.findByText(/No MCP servers/)).toBeInTheDocument();
  });

  it("searches memory by re-fetching with the query", async () => {
    const inspectMemory = vi.fn().mockResolvedValue([
      { type: "user", name: "pref", description: "d", snippet: "s" },
    ]);
    render(<InspectionPanel client={stubClient({ inspectMemory })} />);
    fireEvent.click(screen.getByRole("tab", { name: "Memory" }));
    await screen.findByText("pref");
    fireEvent.change(screen.getByLabelText("search memory"), { target: { value: "tabs" } });
    await waitFor(() => expect(inspectMemory).toHaveBeenCalledWith("tabs"));
  });
});
