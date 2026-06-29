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
});
