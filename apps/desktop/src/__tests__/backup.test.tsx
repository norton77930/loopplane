import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "../App";
import type { SidecarTransport } from "../sidecar";

function stubTransport(): SidecarTransport {
  return {
    run: async function* () {
      return;
    },
    answerApproval: () => undefined,
    answerQuestion: () => undefined,
    cancel: () => undefined,
    status: async () => ({ ready: true }),
    dispose: async () => undefined,
    listSessions: async () => [],
    listProjects: async () => [],
    listWorkspaces: async () => [],
    setDraft: () => undefined,
    clearDraft: () => undefined,
    activeSessionId: null,
    activeSubscriptionId: null,
  } as unknown as SidecarTransport;
}

function installDesktopApi(overrides: Record<string, unknown> = {}) {
  const backup = {
    describe: vi.fn().mockResolvedValue({
      format: "loopplane.desktop.backup",
      disclosure_version: 1,
      unencrypted: true,
    }),
    chooseAndCreate: vi.fn().mockResolvedValue({
      finalized: true,
      entry_count: 3,
    }),
    chooseAndValidateRestore: vi.fn().mockResolvedValue({
      restore_token: "opaque-restore-token",
      summary: {
        project_count: 2,
        session_count: 3,
        artifact_count: 1,
        drafts_excluded: true,
        relink_required: true,
      },
    }),
    commitRestore: vi.fn().mockResolvedValue({ committed: true }),
    cancelRestore: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };
  window.loopplaneDesktop = {
    inspection: {
      get: vi
        .fn()
        .mockResolvedValue({ skills: [], tools: [], mcp: [], memory: [] }),
    },
    agentControls: {
      get: vi.fn().mockResolvedValue({
        default_mode: null,
        selectable_modes: [],
        budget: {},
        actions: [],
      }),
    },
    capabilities: {
      list: vi.fn().mockResolvedValue({ capabilities: [] }),
      invokeAction: vi.fn().mockResolvedValue({ capabilities: [] }),
    },
    audit: {
      list: vi.fn().mockResolvedValue({
        session_id: "session",
        entries: [],
        next_cursor: null,
      }),
    },
    backup,
  } as never;
  return backup;
}

function desktopError() {
  return Object.assign(
    new Error("raw private failure X:\\private\\restore.zip"),
    {
      desktop: {
        category: "busy",
        messageKey: "backup.error.profile_busy",
        retryable: true,
        recovery: "wait",
      },
    },
  );
}

const previousApi = window.loopplaneDesktop;

afterEach(() => {
  window.loopplaneDesktop = previousApi;
});

describe("Desktop backup and restore view", () => {
  it("requires the unencrypted content disclosure and states draft exclusion", async () => {
    const backup = installDesktopApi();
    render(<App transport={stubTransport()} />);

    fireEvent.click(screen.getByRole("button", { name: "Backup and restore" }));
    expect(screen.getByText(/backup is unencrypted/i)).toBeInTheDocument();
    expect(
      screen.getByText(/user, model, and tool conversation content/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/eligible artifacts/i)).toBeInTheDocument();
    expect(screen.getByText(/unsent drafts are excluded/i)).toBeInTheDocument();

    const create = screen.getByRole("button", {
      name: "Choose backup destination",
    });
    expect(create).toBeDisabled();
    fireEvent.click(
      screen.getByRole("checkbox", {
        name: "I understand this backup is unencrypted",
      }),
    );
    expect(create).toBeEnabled();
    fireEvent.click(create);

    await waitFor(() =>
      expect(backup.chooseAndCreate).toHaveBeenCalledWith({
        acknowledgement: true,
      }),
    );
    expect(await screen.findByRole("status")).toHaveTextContent(
      /backup complete/i,
    );
    expect(document.body).not.toHaveTextContent("X:\\private");
  });

  it("previews counts, reservation, draft exclusion, and relink before commit", async () => {
    const backup = installDesktopApi();
    render(<App transport={stubTransport()} />);

    fireEvent.click(screen.getByRole("button", { name: "Backup and restore" }));
    fireEvent.click(
      screen.getByRole("button", { name: "Choose backup to restore" }),
    );

    await waitFor(() =>
      expect(backup.chooseAndValidateRestore).toHaveBeenCalledOnce(),
    );
    expect(
      await screen.findByText(/restore reservation active/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/projects: 2/i)).toBeInTheDocument();
    expect(screen.getByText(/sessions: 3/i)).toBeInTheDocument();
    expect(screen.getByText(/artifacts: 1/i)).toBeInTheDocument();
    expect(screen.getByText(/unsent drafts excluded/i)).toBeInTheDocument();
    expect(screen.getByText(/workspace relink required/i)).toBeInTheDocument();

    const commit = screen.getByRole("button", { name: "Commit restore" });
    expect(commit).toBeDisabled();
    fireEvent.click(
      screen.getByRole("checkbox", { name: "Replace this profile" }),
    );
    fireEvent.click(commit);

    await waitFor(() =>
      expect(backup.commitRestore).toHaveBeenCalledWith(
        "opaque-restore-token",
        true,
      ),
    );
  });

  it("renders only the fixed public-safe error projection", async () => {
    const backup = installDesktopApi({
      chooseAndValidateRestore: vi.fn().mockRejectedValue(desktopError()),
    });
    render(<App transport={stubTransport()} />);

    fireEvent.click(screen.getByRole("button", { name: "Backup and restore" }));
    fireEvent.click(
      screen.getByRole("button", { name: "Choose backup to restore" }),
    );

    await waitFor(() =>
      expect(backup.chooseAndValidateRestore).toHaveBeenCalledOnce(),
    );
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/busy|wait/i);
    expect(alert).not.toHaveTextContent("raw private failure");
    expect(alert).not.toHaveTextContent("X:\\private\\restore.zip");
  });
});
