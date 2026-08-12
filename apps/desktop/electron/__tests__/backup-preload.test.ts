/**
 * Backup/restore IPC serialization through the public preload facade (078 T079).
 */

import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

const electron = vi.hoisted(() => ({
  exposed: {} as Record<string, unknown>,
  invoke: vi.fn(),
  on: vi.fn(),
  removeListener: vi.fn(),
}));

vi.mock("electron", () => ({
  contextBridge: {
    exposeInMainWorld(name: string, value: unknown) {
      electron.exposed[name] = value;
    },
  },
  ipcRenderer: {
    invoke: electron.invoke,
    on: electron.on,
    removeListener: electron.removeListener,
  },
}));

type BackupFacade = {
  describe(): Promise<unknown>;
  cancelRestore(restoreToken: string): Promise<void>;
};

type ExposedDesktopApi = {
  backup: BackupFacade;
};

function backupFacade(): BackupFacade {
  return (electron.exposed.loopplaneDesktop as ExposedDesktopApi).backup;
}

async function rejectedDesktopError(promise: Promise<unknown>) {
  try {
    await promise;
  } catch (error) {
    return error as Error & {
      desktop: {
        category: string;
        messageKey: string;
        retryable: boolean;
        recovery?: string;
      };
    };
  }
  throw new Error("expected rejection");
}

beforeAll(async () => {
  await import("../preload");
});

beforeEach(() => {
  electron.invoke.mockReset();
});

describe("backup/restore preload serialization", () => {
  it("unwraps structured-cloned success and rehydrates a typed public error", async () => {
    electron.invoke.mockResolvedValueOnce(
      structuredClone({
        ok: true,
        value: {
          disclosure: "Backups are not application-encrypted.",
          includes: ["session_checkpoints"],
          excludes: ["workspace_bindings"],
          format: "loopplane.desktop.backup",
          schema_version: 1,
        },
      }),
    );
    await expect(backupFacade().describe()).resolves.toEqual({
      disclosure: "Backups are not application-encrypted.",
      includes: ["session_checkpoints"],
      excludes: ["workspace_bindings"],
      format: "loopplane.desktop.backup",
      schema_version: 1,
    });

    electron.invoke.mockResolvedValueOnce(
      structuredClone({
        ok: false,
        error: {
          category: "publication_failed",
          messageKey: "restore.error.publication_failed_restart",
          retryable: false,
          recovery: "restart_runtime",
        },
      }),
    );
    const error = await rejectedDesktopError(backupFacade().describe());
    expect(error.message).toBe("restore.error.publication_failed_restart");
    expect(error.desktop).toEqual({
      category: "publication_failed",
      messageKey: "restore.error.publication_failed_restart",
      retryable: false,
      recovery: "restart_runtime",
    });
  });

  it("resolves cancelRestore only as void", async () => {
    electron.invoke.mockResolvedValueOnce(
      structuredClone({
        ok: true,
        value: { cancelled: true, restore_token: "opaque-token" },
      }),
    );

    await expect(
      backupFacade().cancelRestore("opaque-token"),
    ).resolves.toBeUndefined();
    expect(electron.invoke).toHaveBeenCalledWith("lp:restore:cancel", {
      restoreToken: "opaque-token",
    });
  });

  it("contains Electron transport rejection with the sole public fallback", async () => {
    electron.invoke.mockRejectedValueOnce(
      new Error("raw lp:backup:describe X:\\private\\archive.zip"),
    );

    const error = await rejectedDesktopError(backupFacade().describe());
    expect(error.message).toBe("desktop.error.internal_failure");
    expect(error.desktop).toEqual({
      category: "internal_failure",
      messageKey: "desktop.error.internal_failure",
      retryable: true,
      recovery: "restart_runtime",
    });
    expect(JSON.stringify(error.desktop)).not.toContain("private");
    expect(JSON.stringify(error.desktop)).not.toContain("lp:backup");
  });

  it("contains malformed envelopes with the sole public fallback", async () => {
    electron.invoke.mockResolvedValueOnce(
      structuredClone({
        ok: false,
        error: {
          category: "unsafe_input",
          messageKey: "backup.error.unsafe_archive",
          retryable: false,
          privatePath: "X:\\private\\secret.zip",
        },
      }),
    );

    const error = await rejectedDesktopError(backupFacade().describe());
    expect(error.message).toBe("desktop.error.internal_failure");
    expect(error.desktop).toEqual({
      category: "internal_failure",
      messageKey: "desktop.error.internal_failure",
      retryable: true,
      recovery: "restart_runtime",
    });
    expect(JSON.stringify(error.desktop)).not.toContain("private");

    electron.invoke.mockResolvedValueOnce(
      structuredClone({
        ok: false,
        error: {
          category: "unsafe_archive",
          messageKey: "backup.error.unsafe_archive",
          retryable: false,
        },
      }),
    );
    const causeLabelError = await rejectedDesktopError(
      backupFacade().describe(),
    );
    expect(causeLabelError.message).toBe("desktop.error.internal_failure");
    expect(causeLabelError.desktop).toEqual({
      category: "internal_failure",
      messageKey: "desktop.error.internal_failure",
      retryable: true,
      recovery: "restart_runtime",
    });
  });
});
