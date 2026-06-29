import { fireEvent, render, screen } from "@testing-library/react";

import type { ApiClient } from "../api/client";
import { App } from "../App";

function makeClient(): ApiClient {
  return {
    listSessions: async () => [],
    listModels: async () => [],
    history: async () => [],
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

  it("shows the active session workspace context", async () => {
    render(
      <App
        client={
          {
            ...makeClient(),
            listSessions: async () => [
              {
                session_id: "s1",
                label: "Alpha",
                created_at: new Date().toISOString(),
                last_active_at: new Date().toISOString(),
                context_id: "Docs",
                context_name: "Docs",
                context_workspace_label: "docs-repo",
                context_status: "available",
              },
            ],
          } as unknown as ApiClient
        }
      />,
    );

    fireEvent.click(await screen.findByText("Alpha"));

    expect(await screen.findByText("Context: Docs")).toBeInTheDocument();
  });
});
