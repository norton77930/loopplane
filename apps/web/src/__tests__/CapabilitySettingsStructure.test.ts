declare global {
  interface ImportMeta {
    glob<T = unknown>(
      pattern: string,
      options: { eager: true; import: string; query: string },
    ): Record<string, T>;
  }
}

const categoryModules = import.meta.glob<string>(
  "../components/settings/*Settings.tsx",
  { eager: true, import: "default", query: "?raw" },
);
const orchestratorSource = import.meta.glob<string>(
  "../components/CapabilitySettingsView.tsx",
  { eager: true, import: "default", query: "?raw" },
);
const capabilityEntrypoints = import.meta.glob<string>(
  "../components/CapabilitySettings*.tsx",
  { eager: true, import: "default", query: "?raw" },
);

describe("CapabilitySettingsView structure", () => {
  it("keeps only the gated settings workspace entrypoint", () => {
    expect(Object.keys(capabilityEntrypoints)).toEqual([
      "../components/CapabilitySettingsView.tsx",
    ]);
  });

  it("keeps the seven settings categories in private focused modules", () => {
    expect(Object.keys(categoryModules).sort()).toEqual([
      "../components/settings/AgentControlsSettings.tsx",
      "../components/settings/McpSettings.tsx",
      "../components/settings/MemorySettings.tsx",
      "../components/settings/ModelDefaultSettings.tsx",
      "../components/settings/ScheduleSettings.tsx",
      "../components/settings/SkillSettings.tsx",
      "../components/settings/WorkspaceSettings.tsx",
    ]);

    const source = Object.values(orchestratorSource)[0];
    expect(source).toBeDefined();
    expect(source).not.toMatch(
      /function (AgentControls|Memory|Skill|Mcp|Workspace|Schedule|ModelDefault)Settings/,
    );
  });
});
