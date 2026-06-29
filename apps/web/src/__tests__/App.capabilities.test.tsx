import { fireEvent, render, screen } from "@testing-library/react";

import type { ApiClient } from "../api/client";
import { App } from "../App";

function makeClient(): ApiClient {
  return {
    listSessions: async () => [],
    listModels: async () => [],
    inspectSkills: async () => ({ skills: [], problems: [] }),
    inspectTools: async () => [],
    inspectMcp: async () => [],
    inspectMemory: async () => [],
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

describe("App capability settings routing", () => {
  it("keeps the chat composer while opening capability settings", async () => {
    render(<App client={makeClient()} />);

    fireEvent.click(screen.getByText("Inspect"));

    expect(await screen.findByRole("tab", { name: "Capabilities" })).toBeInTheDocument();
    expect(screen.getByLabelText("prompt")).toBeInTheDocument();
  });
});
