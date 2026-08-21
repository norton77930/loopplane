import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { McpSettings } from "../components/settings/McpSettings";
import { MemorySettings } from "../components/settings/MemorySettings";
import { ModelDefaultSettings } from "../components/settings/ModelDefaultSettings";
import { ScheduleSettings } from "../components/settings/ScheduleSettings";
import { SkillSettings } from "../components/settings/SkillSettings";
import { WorkspaceSettings } from "../components/settings/WorkspaceSettings";

declare global {
  interface ImportMeta {
    glob<T = unknown>(
      pattern: string,
      options: { eager: true; import: string; query: string },
    ): Record<string, T>;
  }
}

// 083 Wave 3 (FR-020): every settings module living in the shared package must
// render from an injected service and never name a transport. The raw-source
// scan mirrors apps/web's CapabilitySettingsStructure technique.
const movedSources = import.meta.glob<string>(
  "../components/settings/*.tsx",
  { eager: true, import: "default", query: "?raw" },
);

const ok = async () => ({ ok: true, message: "" });

async function expectRendersEmpty(
  container: HTMLElement,
  list: ReturnType<typeof vi.fn>,
) {
  await waitFor(() =>
    expect(container.querySelector(".capability-empty")).not.toBeNull(),
  );
  expect(list).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("heading", { level: 2 })).toBeInTheDocument();
}

describe("settings ports (083 Wave 3)", () => {
  it("keeps every shared settings module transport-free", () => {
    const files = Object.keys(movedSources);
    // The six moved panels + AgentControlsSettings + CapabilityDetail + EmptySection.
    expect(files.length).toBeGreaterThanOrEqual(9);
    for (const [file, source] of Object.entries(movedSources)) {
      expect(source, file).not.toMatch(/api\/client|ApiClient|fetch\(|axios/);
    }
  });

  it("renders McpSettings from an injected service", async () => {
    const list = vi.fn(async () => []);
    const { container } = render(
      <McpSettings
        service={{
          list,
          get: async () => ({ name: "srv" }),
          upsert: ok,
          reconnect: ok,
          remove: ok,
        }}
        canMutate
      />,
    );
    await expectRendersEmpty(container, list);
  });

  it("renders MemorySettings from an injected service", async () => {
    const list = vi.fn(async () => []);
    const { container } = render(
      <MemorySettings
        service={{
          list,
          get: async () => ({ id: "m", name: "m", actions: [], content: "" }),
          write: ok,
          remove: ok,
        }}
        canMutate
      />,
    );
    await expectRendersEmpty(container, list);
  });

  it("filters memory entries client-side when searchable (083 FR-008)", async () => {
    const entries = [
      { id: "m1", name: "alpha prefs", actions: [] },
      { id: "m2", name: "beta prefs", actions: [] },
    ];
    render(
      <MemorySettings
        service={{
          list: async () => entries,
          get: async () => ({ id: "m1", name: "alpha prefs", actions: [], content: "" }),
          write: ok,
          remove: ok,
        }}
        canMutate
        searchable
      />,
    );
    await waitFor(() =>
      expect(screen.getByTestId("memory-m1")).toBeInTheDocument(),
    );
    fireEvent.change(screen.getByRole("searchbox"), {
      target: { value: "alpha" },
    });
    expect(screen.getByTestId("memory-m1")).toBeInTheDocument();
    expect(screen.queryByTestId("memory-m2")).toBeNull();
    fireEvent.change(screen.getByRole("searchbox"), {
      target: { value: "zzz" },
    });
    expect(screen.queryByTestId("memory-m1")).toBeNull();
  });

  it("renders SkillSettings from an injected service", async () => {
    const list = vi.fn(async () => []);
    const { container } = render(
      <SkillSettings
        service={{
          list,
          get: async () => ({
            id: "s",
            name: "s",
            actions: [],
            instructions: "",
          }),
          write: ok,
          import: ok,
          remove: ok,
        }}
        canMutate
      />,
    );
    await expectRendersEmpty(container, list);
  });

  it("renders ScheduleSettings from an injected service", async () => {
    const list = vi.fn(async () => []);
    const { container } = render(
      <ScheduleSettings
        service={{
          list,
          get: async () => ({
            id: "c",
            name: "c",
            trigger: "daily",
            actions: [],
            instruction: "",
            enabled: true,
          }),
          upsert: ok,
          runNow: ok,
          enable: ok,
          disable: ok,
          remove: ok,
        }}
        canMutate
      />,
    );
    await expectRendersEmpty(container, list);
  });

  it("renders WorkspaceSettings from an injected service", async () => {
    const list = vi.fn(async () => []);
    const { container } = render(
      <WorkspaceSettings
        service={{
          list,
          get: async () => ({
            id: "w",
            name: "w",
            workspace_label: "docs",
            actions: [],
          }),
          upsert: ok,
          bind: async () => ({}),
          remove: ok,
        }}
        canMutate
      />,
    );
    await expectRendersEmpty(container, list);
  });

  it("renders ModelDefaultSettings from an injected service", async () => {
    const listModels = vi.fn(async () => []);
    const { container } = render(
      <ModelDefaultSettings
        service={{
          listModels,
          getDefault: async () => ({ status: "unavailable" }),
          setDefault: ok,
          clearDefault: ok,
        }}
        canMutate
      />,
    );
    await waitFor(() =>
      expect(container.querySelector(".capability-empty")).not.toBeNull(),
    );
    expect(listModels).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("heading", { level: 2 })).toBeInTheDocument();
  });
});
