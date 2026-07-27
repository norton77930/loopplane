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
    getCapabilitySettings: async () => ({
      storage_available: true,
      mutations_enabled: true,
      runtime_activation_enabled: true,
      mcp_endpoint_policy_available: true,
      schedule_runner_available: true,
    }),
  } as unknown as ApiClient;
}

describe("App capability settings routing", () => {
  it("keeps inspection read only and preserves the chat composer", async () => {
    render(<App client={makeClient()} />);

    fireEvent.click(screen.getByText("Inspect"));

    expect(await screen.findByRole("tab", { name: "Skills" })).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Capabilities" })).toBeNull();
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

  it("toggles an independent settings workspace without unmounting shell controls", async () => {
    render(<App client={makeClient()} />);

    expect(await screen.findByTestId("messages")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("prompt"), {
      target: { value: "preserve this draft" },
    });
    const settingsButton = screen.getByRole("button", { name: "Settings" });
    settingsButton.focus();
    fireEvent.click(settingsButton);

    expect(
      await screen.findByRole("heading", { name: "Capability settings" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("messages").closest(".conversation-view")).toHaveAttribute(
      "hidden",
    );
    expect(screen.getByLabelText("prompt")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Inspect" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /New chat/ }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Back to chat" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Inspect" }));
    expect(await screen.findByRole("tab", { name: "Tools" })).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Capability settings" }),
    ).toBeInTheDocument();

    const backButton = screen.getByRole("button", { name: "Back to chat" });
    backButton.focus();
    fireEvent.click(backButton);
    expect(await screen.findByTestId("messages")).toBeInTheDocument();
    expect(screen.getByLabelText("prompt")).toHaveValue("preserve this draft");
    expect(
      screen.queryByRole("heading", { name: "Capability settings" }),
    ).toBeNull();
    expect(document.activeElement).toBe(settingsButton);
  });

  it("keeps the conversation region mounted so its scroll state survives Settings", async () => {
    render(<App client={makeClient()} />);
    const region = await screen.findByTestId("messages");
    Object.defineProperty(region, "scrollHeight", { value: 1200, configurable: true });
    Object.defineProperty(region, "clientHeight", { value: 400, configurable: true });
    Object.defineProperty(region, "scrollTop", {
      value: 320,
      writable: true,
      configurable: true,
    });
    fireEvent.scroll(region);

    fireEvent.click(screen.getByRole("button", { name: "Settings" }));
    fireEvent.click(await screen.findByRole("button", { name: "Back to chat" }));

    expect(screen.getByTestId("messages")).toBe(region);
    expect(region.scrollTop).toBe(320);
  });
});
