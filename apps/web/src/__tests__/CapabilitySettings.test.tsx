import { render, screen } from "@testing-library/react";

import type { ApiClient } from "../api/client";
import { CapabilitySettings } from "../components/CapabilitySettings";

function stubClient(): ApiClient {
  return {
    listMemoryEntries: async () => [],
    listManagedSkills: async () => [],
    listMcpConfigurations: async () => [],
    listWorkspaceContexts: async () => [],
    listSchedules: async () => [],
    getModelDefault: async () => ({
      model_id: null,
      label: null,
      status: "fallback",
      updated_at: null,
    }),
  } as unknown as ApiClient;
}

describe("CapabilitySettings", () => {
  it("loads the capability management sections", async () => {
    render(<CapabilitySettings client={stubClient()} />);

    expect(await screen.findByText("Memory")).toBeInTheDocument();
    expect(screen.getByText("Skills")).toBeInTheDocument();
    expect(screen.getByText("MCP")).toBeInTheDocument();
    expect(screen.getByText("Workspace")).toBeInTheDocument();
    expect(screen.getByText("Schedules")).toBeInTheDocument();
    expect(screen.getByText("Model default")).toBeInTheDocument();
  });
});
