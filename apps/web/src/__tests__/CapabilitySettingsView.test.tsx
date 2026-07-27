import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";

import type { ApiClient } from "../api/client";
import { CapabilitySettingsView } from "../components/CapabilitySettingsView";
import { I18nProvider } from "../i18n/i18n";
import {
  capabilitySettingsFixtures,
  createCapabilitySettingsClient,
} from "./capabilitySettingsHelpers";

describe("CapabilitySettingsView", () => {
  it("distinguishes settings-status loading and failure from policy read only", async () => {
    const loadingClient = {
      ...createCapabilitySettingsClient(),
      getCapabilitySettings: () => new Promise(() => undefined),
      listMemoryEntries: () => new Promise(() => undefined),
    } as unknown as ApiClient;
    const loading = render(<CapabilitySettingsView client={loadingClient} />);

    expect(screen.getByRole("status")).toHaveTextContent("Loading");
    expect(within(screen.getByRole("banner")).queryByText("Read only")).toBeNull();
    loading.unmount();

    const failedClient = {
      ...createCapabilitySettingsClient(),
      getCapabilitySettings: async () => {
        throw new Error("offline");
      },
    } as unknown as ApiClient;
    render(<CapabilitySettingsView client={failedClient} />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Settings status is unavailable",
    );
    expect(within(screen.getByRole("banner")).queryByText("Read only")).toBeNull();
  });

  it("renders an independent settings workspace with section tabs", async () => {
    render(
      <CapabilitySettingsView client={createCapabilitySettingsClient()} />,
    );

    expect(
      await screen.findByRole("heading", { name: "Capability settings" }),
    ).toBeInTheDocument();
    for (const name of [
      "Agent controls",
      "Memory",
      "Skills",
      "MCP",
      "Workspace",
      "Schedules",
      "Model default",
    ]) {
      expect(screen.getByRole("tab", { name })).toBeInTheDocument();
    }
    expect(
      screen.getByRole("tablist", { name: "Settings categories" }),
    ).toHaveAttribute("aria-orientation", "vertical");
    expect(screen.getByRole("tabpanel", { name: "Memory" })).toBeInTheDocument();
  });

  it("manages owned memory and keeps shared memory read only", async () => {
    const listMemoryEntries = vi
      .fn()
      .mockResolvedValue(structuredClone(capabilitySettingsFixtures.memory));
    const listManagedSkills = vi.fn();
    const writeMemoryEntry = vi.fn().mockResolvedValue({ result: { ok: true } });
    const deleteMemoryEntry = vi.fn().mockResolvedValue({ ok: true });
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    const client = {
      ...createCapabilitySettingsClient(),
      listMemoryEntries,
      listManagedSkills,
      writeMemoryEntry,
      deleteMemoryEntry,
    } as unknown as ApiClient;

    render(<CapabilitySettingsView client={client} />);

    const owned = within(await screen.findByTestId("memory-pref"));
    const shared = within(screen.getByTestId("memory-host-guide"));
    expect(shared.getByText("Read only")).toBeInTheDocument();
    expect(shared.queryByRole("button", { name: "Delete" })).toBeNull();

    fireEvent.change(screen.getByLabelText("Memory name"), {
      target: { value: "new-memory" },
    });
    fireEvent.change(screen.getByLabelText("Memory content"), {
      target: { value: "new private note" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save memory" }));

    await waitFor(() =>
      expect(writeMemoryEntry).toHaveBeenCalledWith({
        name: "new-memory",
        kind: "user",
        description: "",
        content: "new private note",
      }),
    );
    await waitFor(() => expect(listMemoryEntries).toHaveBeenCalledTimes(2));
    expect(listManagedSkills).not.toHaveBeenCalled();

    fireEvent.click(owned.getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(deleteMemoryEntry).toHaveBeenCalledWith("pref"));
    await waitFor(() => expect(listMemoryEntries).toHaveBeenCalledTimes(3));
    expect(confirm).toHaveBeenCalled();
    confirm.mockRestore();
  });

  it("opens shared memory in a safe read-only detail and restores focus", async () => {
    const client = createCapabilitySettingsClient();

    render(<CapabilitySettingsView client={client} />);

    const shared = within(await screen.findByTestId("memory-host-guide"));
    const open = shared.getByRole("button", { name: "Open" });
    open.focus();
    fireEvent.click(open);

    const dialog = await screen.findByRole("dialog", {
      name: "host-guide details",
    });
    expect(within(dialog).getByText("shared")).toBeInTheDocument();
    expect(within(dialog).getByText("host guidance")).toBeInTheDocument();
    expect(within(dialog).getByText("shared guidance")).toBeInTheDocument();
    expect(within(dialog).queryByText("private full shared memory")).toBeNull();
    expect(screen.getByLabelText("Memory name")).toHaveValue("");
    expect(screen.getByLabelText("Memory content")).toHaveValue("");

    fireEvent.keyDown(dialog, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(open).toHaveFocus();
  });

  it("shows only allow-listed shared skill and MCP detail fields", async () => {
    render(<CapabilitySettingsView client={createCapabilitySettingsClient()} />);

    fireEvent.click(screen.getByRole("tab", { name: "Skills" }));
    const sharedSkill = within(await screen.findByTestId("skill-host-reviewer"));
    fireEvent.click(sharedSkill.getByRole("button", { name: "Open" }));

    let dialog = await screen.findByRole("dialog", {
      name: "host-reviewer details",
    });
    expect(within(dialog).getByText("reviews notes")).toBeInTheDocument();
    expect(within(dialog).getByText("host")).toBeInTheDocument();
    expect(within(dialog).queryByText("private shared instructions")).toBeNull();
    fireEvent.click(within(dialog).getByRole("button", { name: "Close" }));

    fireEvent.click(screen.getByRole("tab", { name: "MCP" }));
    const sharedMcp = within(await screen.findByTestId("mcp-host-search"));
    fireEvent.click(sharedMcp.getByRole("button", { name: "Open" }));

    dialog = await screen.findByRole("dialog", {
      name: "host-search details",
    });
    expect(within(dialog).getByText("http")).toBeInTheDocument();
    expect(within(dialog).getByText("connected")).toBeInTheDocument();
    expect(within(dialog).getByText("search")).toBeInTheDocument();
    expect(within(dialog).queryByText("https://private.example.invalid/secret")).toBeNull();
    expect(screen.getByLabelText("MCP name")).toHaveValue("");
    expect(screen.getByLabelText("MCP endpoint")).toHaveValue("");
  });

  it("opens and binds an allowed workspace context from projected actions", async () => {
    const bindSessionContext = vi.fn().mockResolvedValue({
      session_id: "session-1",
      context_id: "SharedDocs",
      name: "Shared docs",
      workspace_label: "shared-docs",
      status: "read_only",
    });
    const client = createCapabilitySettingsClient({ bindSessionContext });

    render(<CapabilitySettingsView client={client} sessionId="session-1" />);
    fireEvent.click(screen.getByRole("tab", { name: "Workspace" }));

    const shared = within(await screen.findByTestId("context-SharedDocs"));
    fireEvent.click(shared.getByRole("button", { name: "Open" }));
    const dialog = await screen.findByRole("dialog", {
      name: "Shared docs details",
    });
    expect(within(dialog).getByText("shared documentation workspace")).toBeInTheDocument();
    expect(within(dialog).getByText("shared-docs")).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: "Bind" }));

    await waitFor(() =>
      expect(bindSessionContext).toHaveBeenCalledWith("session-1", "SharedDocs"),
    );
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("keeps action-driven shared Open available when mutations are disabled", async () => {
    const client = createCapabilitySettingsClient({
      getCapabilitySettings: async () => ({
        ...structuredClone(capabilitySettingsFixtures.settings),
        mutations_enabled: false,
      }),
      listMemoryEntries: async () => [
        {
          ...structuredClone(capabilitySettingsFixtures.memory[1]),
          actions: ["open"],
        },
      ],
    });

    render(<CapabilitySettingsView client={client} />);

    const shared = within(await screen.findByTestId("memory-host-guide"));
    expect(shared.getByRole("button", { name: "Open" })).toBeEnabled();
    fireEvent.click(shared.getByRole("button", { name: "Open" }));
    expect(
      await screen.findByRole("dialog", {
        name: "host-guide details",
      }),
    ).toBeInTheDocument();
  });

  it("shows a public-safe memory delete refusal without refreshing", async () => {
    const listMemoryEntries = vi
      .fn()
      .mockResolvedValue(structuredClone(capabilitySettingsFixtures.memory));
    const deleteMemoryEntry = vi.fn().mockResolvedValue({
      ok: false,
      status: "disabled_by_policy",
      message: "Capability mutations are disabled.",
    });
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    const client = {
      ...createCapabilitySettingsClient(),
      listMemoryEntries,
      deleteMemoryEntry,
    } as unknown as ApiClient;

    render(<CapabilitySettingsView client={client} />);
    const owned = within(await screen.findByTestId("memory-pref"));
    fireEvent.click(owned.getByRole("button", { name: "Delete" }));

    expect(
      await screen.findByText("Capability mutations are disabled."),
    ).toBeInTheDocument();
    expect(deleteMemoryEntry).toHaveBeenCalledWith("pref");
    expect(listMemoryEntries).toHaveBeenCalledTimes(1);
    confirm.mockRestore();
  });

  it("creates, imports, and deletes owned skills without mutating shared skills", async () => {
    const listManagedSkills = vi
      .fn()
      .mockResolvedValue(structuredClone(capabilitySettingsFixtures.skills));
    const writeManagedSkill = vi.fn().mockResolvedValue({ result: { ok: true } });
    const importManagedSkill = vi.fn().mockResolvedValue({ result: { ok: true } });
    const deleteManagedSkill = vi.fn().mockResolvedValue({ ok: true });
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    const client = {
      ...createCapabilitySettingsClient(),
      listManagedSkills,
      writeManagedSkill,
      importManagedSkill,
      deleteManagedSkill,
    } as unknown as ApiClient;

    render(<CapabilitySettingsView client={client} />);
    fireEvent.click(screen.getByRole("tab", { name: "Skills" }));

    const owned = within(await screen.findByTestId("skill-writer"));
    const shared = within(screen.getByTestId("skill-host-reviewer"));
    expect(shared.getByText("Read only")).toBeInTheDocument();
    expect(shared.queryByRole("button", { name: "Delete" })).toBeNull();

    fireEvent.change(screen.getByLabelText("Skill name"), {
      target: { value: "editor" },
    });
    fireEvent.change(screen.getByLabelText("Skill instructions"), {
      target: { value: "edit the draft" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save skill" }));
    await waitFor(() =>
      expect(writeManagedSkill).toHaveBeenCalledWith({
        name: "editor",
        description: "",
        instructions: "edit the draft",
      }),
    );

    fireEvent.click(screen.getByRole("button", { name: "Import skill" }));
    await waitFor(() =>
      expect(importManagedSkill).toHaveBeenCalledWith({
        name: "editor",
        description: "",
        instructions: "edit the draft",
      }),
    );
    fireEvent.click(owned.getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(deleteManagedSkill).toHaveBeenCalledWith("writer"));
    await waitFor(() => expect(listManagedSkills).toHaveBeenCalledTimes(4));
    expect(confirm).toHaveBeenCalled();
    confirm.mockRestore();
  });

  it("shows a public-safe skill delete refusal without refreshing", async () => {
    const listManagedSkills = vi
      .fn()
      .mockResolvedValue(structuredClone(capabilitySettingsFixtures.skills));
    const deleteManagedSkill = vi.fn().mockResolvedValue({
      ok: false,
      status: "disabled_by_policy",
      message: "Capability mutations are disabled.",
    });
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    const client = {
      ...createCapabilitySettingsClient(),
      listManagedSkills,
      deleteManagedSkill,
    } as unknown as ApiClient;

    render(<CapabilitySettingsView client={client} />);
    fireEvent.click(screen.getByRole("tab", { name: "Skills" }));
    const owned = within(await screen.findByTestId("skill-writer"));
    fireEvent.click(owned.getByRole("button", { name: "Delete" }));

    expect(
      await screen.findByText("Capability mutations are disabled."),
    ).toBeInTheDocument();
    expect(deleteManagedSkill).toHaveBeenCalledWith("writer");
    expect(listManagedSkills).toHaveBeenCalledTimes(1);
    confirm.mockRestore();
  });

  it("manages owned MCP connections and keeps shared MCP read only", async () => {
    const listMcpConfigurations = vi
      .fn()
      .mockResolvedValue(structuredClone(capabilitySettingsFixtures.mcp));
    const upsertMcpConfiguration = vi
      .fn()
      .mockResolvedValue({ result: { ok: true } });
    const reconnectMcpConfiguration = vi
      .fn()
      .mockResolvedValue({ ok: true });
    const deleteMcpConfiguration = vi.fn().mockResolvedValue({ ok: true });
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    const client = {
      ...createCapabilitySettingsClient(),
      listMcpConfigurations,
      upsertMcpConfiguration,
      reconnectMcpConfiguration,
      deleteMcpConfiguration,
    } as unknown as ApiClient;

    render(<CapabilitySettingsView client={client} />);
    fireEvent.click(screen.getByRole("tab", { name: "MCP" }));

    const owned = within(await screen.findByTestId("mcp-docs"));
    const shared = within(screen.getByTestId("mcp-host-search"));
    expect(shared.getByText("Read only")).toBeInTheDocument();
    expect(shared.queryByRole("button", { name: "Reconnect" })).toBeNull();

    fireEvent.change(screen.getByLabelText("MCP name"), {
      target: { value: "search" },
    });
    fireEvent.change(screen.getByLabelText("MCP endpoint"), {
      target: { value: "https://mcp.example.invalid" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save MCP" }));
    await waitFor(() =>
      expect(upsertMcpConfiguration).toHaveBeenCalledWith({
        name: "search",
        transport: "http",
        url: "https://mcp.example.invalid",
      }),
    );
    await waitFor(() => expect(listMcpConfigurations).toHaveBeenCalledTimes(2));

    fireEvent.click(owned.getByRole("button", { name: "Reconnect" }));
    await waitFor(() =>
      expect(reconnectMcpConfiguration).toHaveBeenCalledWith("docs"),
    );
    await waitFor(() => expect(listMcpConfigurations).toHaveBeenCalledTimes(3));

    fireEvent.click(owned.getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(deleteMcpConfiguration).toHaveBeenCalledWith("docs"));
    await waitFor(() => expect(listMcpConfigurations).toHaveBeenCalledTimes(4));
    expect(confirm).toHaveBeenCalled();
    confirm.mockRestore();
  });

  it("creates, binds, and deletes owned workspace contexts", async () => {
    const listWorkspaceContexts = vi
      .fn()
      .mockResolvedValue(structuredClone(capabilitySettingsFixtures.contexts));
    const upsertWorkspaceContext = vi
      .fn()
      .mockResolvedValue({ result: { ok: true } });
    const bindSessionContext = vi.fn().mockResolvedValue({ context_id: "Docs" });
    const deleteWorkspaceContext = vi.fn().mockResolvedValue({ ok: true });
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    const client = {
      ...createCapabilitySettingsClient(),
      listWorkspaceContexts,
      upsertWorkspaceContext,
      bindSessionContext,
      deleteWorkspaceContext,
    } as unknown as ApiClient;

    render(<CapabilitySettingsView client={client} sessionId="session-1" />);
    fireEvent.click(screen.getByRole("tab", { name: "Workspace" }));

    const owned = within(await screen.findByTestId("context-Docs"));
    const shared = within(screen.getByTestId("context-SharedDocs"));
    expect(shared.getByText("Read only")).toBeInTheDocument();
    expect(shared.getByRole("button", { name: "Open" })).toBeInTheDocument();
    expect(shared.getByRole("button", { name: "Bind" })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Workspace name"), {
      target: { value: "Product" },
    });
    fireEvent.change(screen.getByLabelText("Workspace label"), {
      target: { value: "product-repo" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save workspace" }));
    await waitFor(() =>
      expect(upsertWorkspaceContext).toHaveBeenCalledWith({
        name: "Product",
        description: "",
        workspace_label: "product-repo",
      }),
    );
    await waitFor(() => expect(listWorkspaceContexts).toHaveBeenCalledTimes(2));

    fireEvent.click(owned.getByRole("button", { name: "Bind" }));
    await waitFor(() =>
      expect(bindSessionContext).toHaveBeenCalledWith("session-1", "Docs"),
    );
    await waitFor(() => expect(listWorkspaceContexts).toHaveBeenCalledTimes(3));

    fireEvent.click(owned.getByRole("button", { name: "Delete" }));
    await waitFor(() =>
      expect(deleteWorkspaceContext).toHaveBeenCalledWith("Docs"),
    );
    await waitFor(() => expect(listWorkspaceContexts).toHaveBeenCalledTimes(4));
    expect(confirm).toHaveBeenCalled();
    confirm.mockRestore();
  });

  it("manages schedules with instruction, run-now, enable, disable, and delete", async () => {
    const enabledSchedule = structuredClone(
      capabilitySettingsFixtures.schedules[0],
    );
    const disabledSchedule = {
      ...structuredClone(capabilitySettingsFixtures.schedules[0]),
      id: "weekly-notes",
      name: "weekly-notes",
      enabled: false,
      status: "disabled",
      actions: ["open", "update", "enable", "delete"],
    };
    const listSchedules = vi
      .fn()
      .mockResolvedValue([enabledSchedule, disabledSchedule]);
    const upsertSchedule = vi
      .fn()
      .mockResolvedValue({ result: { ok: true } });
    const runScheduleNow = vi.fn().mockResolvedValue({ ok: true });
    const enableSchedule = vi.fn().mockResolvedValue({ ok: true });
    const disableSchedule = vi.fn().mockResolvedValue({ ok: true });
    const deleteSchedule = vi.fn().mockResolvedValue({ ok: true });
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    const client = {
      ...createCapabilitySettingsClient(),
      listSchedules,
      upsertSchedule,
      runScheduleNow,
      enableSchedule,
      disableSchedule,
      deleteSchedule,
    } as unknown as ApiClient;

    render(<CapabilitySettingsView client={client} />);
    fireEvent.click(screen.getByRole("tab", { name: "Schedules" }));

    const enabled = within(
      await screen.findByTestId("schedule-daily-notes"),
    );
    const disabled = within(screen.getByTestId("schedule-weekly-notes"));

    fireEvent.change(screen.getByLabelText("Schedule name"), {
      target: { value: "release-notes" },
    });
    fireEvent.change(screen.getByLabelText("Schedule trigger"), {
      target: { value: "manual" },
    });
    fireEvent.change(screen.getByLabelText("Schedule instruction"), {
      target: { value: "refresh release notes" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save schedule" }));
    await waitFor(() =>
      expect(upsertSchedule).toHaveBeenCalledWith({
        name: "release-notes",
        description: "",
        trigger: "manual",
        instruction: "refresh release notes",
        enabled: true,
      }),
    );
    await waitFor(() => expect(listSchedules).toHaveBeenCalledTimes(2));

    fireEvent.click(enabled.getByRole("button", { name: "Run now" }));
    await waitFor(() =>
      expect(runScheduleNow).toHaveBeenCalledWith("daily-notes"),
    );
    await waitFor(() => expect(listSchedules).toHaveBeenCalledTimes(3));

    fireEvent.click(enabled.getByRole("button", { name: "Disable" }));
    await waitFor(() =>
      expect(disableSchedule).toHaveBeenCalledWith("daily-notes"),
    );
    await waitFor(() => expect(listSchedules).toHaveBeenCalledTimes(4));

    fireEvent.click(disabled.getByRole("button", { name: "Enable" }));
    await waitFor(() =>
      expect(enableSchedule).toHaveBeenCalledWith("weekly-notes"),
    );
    await waitFor(() => expect(listSchedules).toHaveBeenCalledTimes(5));

    fireEvent.click(enabled.getByRole("button", { name: "Delete" }));
    await waitFor(() =>
      expect(deleteSchedule).toHaveBeenCalledWith("daily-notes"),
    );
    await waitFor(() => expect(listSchedules).toHaveBeenCalledTimes(6));
    expect(confirm).toHaveBeenCalled();
    confirm.mockRestore();
  });

  it("sets and clears model defaults from the host catalog only", async () => {
    const listModels = vi.fn().mockResolvedValue([
      { id: "fast", label: "Fast model" },
      { id: "slow", label: "Slow model" },
    ]);
    const getModelDefault = vi
      .fn()
      .mockResolvedValue(structuredClone(capabilitySettingsFixtures.modelDefault));
    const setModelDefault = vi
      .fn()
      .mockResolvedValue({ result: { ok: true } });
    const clearModelDefault = vi
      .fn()
      .mockResolvedValue({ result: { ok: true } });
    const client = {
      ...createCapabilitySettingsClient(),
      listModels,
      getModelDefault,
      setModelDefault,
      clearModelDefault,
    } as unknown as ApiClient;

    render(<CapabilitySettingsView client={client} />);
    fireEvent.click(screen.getByRole("tab", { name: "Model default" }));

    const select = await screen.findByLabelText("Default model");
    expect(within(select).getByRole("option", { name: "Fast model" })).toBeInTheDocument();
    expect(within(select).getByRole("option", { name: "Slow model" })).toBeInTheDocument();
    fireEvent.change(select, { target: { value: "slow" } });
    fireEvent.click(screen.getByRole("button", { name: "Save default model" }));
    await waitFor(() => expect(setModelDefault).toHaveBeenCalledWith("slow"));
    await waitFor(() => expect(getModelDefault).toHaveBeenCalledTimes(2));

    fireEvent.click(screen.getByRole("button", { name: "Clear default model" }));
    await waitFor(() => expect(clearModelDefault).toHaveBeenCalled());
    await waitFor(() => expect(getModelDefault).toHaveBeenCalledTimes(3));
    expect(screen.queryByLabelText("Default model id")).toBeNull();
  });

  it("never renders credential or browser-managed stdio controls", async () => {
    render(<CapabilitySettingsView client={createCapabilitySettingsClient()} />);

    fireEvent.click(screen.getByRole("tab", { name: "MCP" }));
    expect(await screen.findByLabelText("MCP transport")).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: /stdio/i })).toBeNull();
    expect(screen.queryByLabelText(/api key/i)).toBeNull();
    expect(screen.queryByLabelText(/credential/i)).toBeNull();
    expect(screen.queryByLabelText(/secret/i)).toBeNull();
    expect(screen.queryByLabelText(/token/i)).toBeNull();
    expect(screen.queryByLabelText(/auth/i)).toBeNull();
  });

  it("renders the settings workspace in Traditional Chinese", async () => {
    localStorage.setItem("loopplane-locale", "zh-TW");
    render(
      <I18nProvider>
        <CapabilitySettingsView client={createCapabilitySettingsClient()} />
      </I18nProvider>,
    );

    expect(
      await screen.findByRole("heading", { name: "\u529f\u80fd\u8a2d\u5b9a" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("tab", { name: "\u8a18\u61b6" }),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText("\u8a18\u61b6\u540d\u7a31"),
    ).toBeInTheDocument();
    expect(screen.getByText("\u552f\u8b80")).toBeInTheDocument();
    localStorage.removeItem("loopplane-locale");
  });
});
