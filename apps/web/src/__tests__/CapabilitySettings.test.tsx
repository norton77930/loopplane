import { fireEvent, render, screen, waitFor } from "@testing-library/react";

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

  it("submits memory and skill management forms", async () => {
    const writeMemoryEntry = vi.fn().mockResolvedValue({ ok: true });
    const writeManagedSkill = vi.fn().mockResolvedValue({ ok: true });
    render(
      <CapabilitySettings
        client={
          {
            ...stubClient(),
            writeMemoryEntry,
            writeManagedSkill,
          } as unknown as ApiClient
        }
      />,
    );

    fireEvent.change(await screen.findByLabelText("memory name"), {
      target: { value: "pref" },
    });
    fireEvent.change(screen.getByLabelText("memory content"), {
      target: { value: "likes tabs" },
    });
    fireEvent.click(screen.getByText("Save memory"));

    fireEvent.change(screen.getByLabelText("skill name"), {
      target: { value: "writer" },
    });
    fireEvent.change(screen.getByLabelText("skill instructions"), {
      target: { value: "write concise notes" },
    });
    fireEvent.click(screen.getByText("Save skill"));

    await waitFor(() =>
      expect(writeMemoryEntry).toHaveBeenCalledWith({
        name: "pref",
        kind: "user",
        description: "",
        content: "likes tabs",
      }),
    );
    expect(writeManagedSkill).toHaveBeenCalledWith({
      name: "writer",
      description: "",
      instructions: "write concise notes",
    });
  });

  it("submits MCP and workspace context management forms", async () => {
    const upsertMcpConfiguration = vi.fn().mockResolvedValue({ ok: true });
    const upsertWorkspaceContext = vi.fn().mockResolvedValue({ ok: true });
    render(
      <CapabilitySettings
        client={
          {
            ...stubClient(),
            upsertMcpConfiguration,
            upsertWorkspaceContext,
          } as unknown as ApiClient
        }
      />,
    );

    fireEvent.change(await screen.findByLabelText("mcp name"), {
      target: { value: "docs" },
    });
    fireEvent.change(screen.getByLabelText("mcp url"), {
      target: { value: "https://mcp.example.invalid" },
    });
    fireEvent.click(screen.getByText("Save MCP"));

    fireEvent.change(screen.getByLabelText("workspace name"), {
      target: { value: "Docs" },
    });
    fireEvent.change(screen.getByLabelText("workspace label"), {
      target: { value: "docs-repo" },
    });
    fireEvent.click(screen.getByText("Save workspace"));

    await waitFor(() =>
      expect(upsertMcpConfiguration).toHaveBeenCalledWith({
        name: "docs",
        transport: "http",
        url: "https://mcp.example.invalid",
      }),
    );
    expect(upsertWorkspaceContext).toHaveBeenCalledWith({
      name: "Docs",
      description: "",
      workspace_label: "docs-repo",
    });
  });
});
