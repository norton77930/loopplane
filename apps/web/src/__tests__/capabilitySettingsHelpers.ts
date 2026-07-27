import type { ApiClient } from "../api/client";

export const capabilitySettingsFixtures = {
  memory: [
    {
      id: "pref",
      name: "pref",
      kind: "user",
      description: "editor preference",
      snippet: "likes tabs",
      status: "available",
      scope: "owned",
      actions: ["open", "update", "delete"],
      problem: null,
      updated_at: null,
    },
    {
      id: "host-guide",
      name: "host-guide",
      kind: "shared",
      description: "host guidance",
      snippet: "shared guidance",
      status: "read_only",
      scope: "shared_read_only",
      actions: ["open"],
      problem: null,
      updated_at: null,
    },
  ],
  skills: [
    {
      id: "writer",
      name: "writer",
      description: "writes notes",
      source: "managed",
      status: "available",
      scope: "owned",
      actions: ["open", "update", "delete"],
      problem: null,
      updated_at: null,
    },
    {
      id: "host-reviewer",
      name: "host-reviewer",
      description: "reviews notes",
      source: "host",
      status: "read_only",
      scope: "shared_read_only",
      actions: ["open"],
      problem: null,
      updated_at: null,
    },
  ],
  mcp: [
    {
      id: "docs",
      name: "docs",
      transport: "http",
      url: "https://mcp.example.invalid",
      status: "disconnected",
      tool_count: 0,
      tools: [],
      scope: "owned",
      actions: ["open", "update", "reconnect", "delete"],
      problem: null,
      updated_at: null,
    },
    {
      id: "host-search",
      name: "host-search",
      transport: "http",
      status: "connected",
      tool_count: 1,
      tools: ["search"],
      scope: "shared_read_only",
      actions: ["open"],
      problem: null,
      updated_at: null,
    },
  ],
  contexts: [
    {
      id: "Docs",
      name: "Docs",
      description: "documentation workspace",
      workspace_label: "docs-repo",
      status: "available",
      scope: "owned",
      actions: ["open", "update", "bind", "delete"],
      problem: null,
      updated_at: null,
    },
    {
      id: "SharedDocs",
      name: "Shared docs",
      description: "shared documentation workspace",
      workspace_label: "shared-docs",
      status: "read_only",
      scope: "shared_read_only",
      actions: ["open", "bind"],
      problem: null,
      updated_at: null,
    },
  ],
  schedules: [
    {
      id: "daily-notes",
      name: "daily-notes",
      description: "refresh notes",
      trigger: "manual",
      instruction: "refresh documentation notes",
      enabled: true,
      status: "enabled",
      scope: "owned",
      actions: ["open", "update", "disable", "run_now", "delete"],
      next_run_at: null,
      last_run_at: null,
      problem: null,
      updated_at: null,
    },
  ],
  modelDefault: {
    model_id: "fast",
    label: "Fast model",
    status: "available",
    scope: "owned",
    actions: ["set", "clear"],
    problem: null,
    updated_at: null,
  },
  settings: {
    storage_available: true,
    mutations_enabled: true,
    runtime_activation_enabled: true,
    mcp_endpoint_policy_available: true,
    schedule_runner_available: true,
  },
  models: [{ id: "fast", label: "Fast model" }],
} as const;

export function createCapabilitySettingsClient(
  overrides: Record<string, unknown> = {},
): ApiClient {
  return {
    listMemoryEntries: async () =>
      structuredClone(capabilitySettingsFixtures.memory),
    listManagedSkills: async () =>
      structuredClone(capabilitySettingsFixtures.skills),
    listMcpConfigurations: async () =>
      structuredClone(capabilitySettingsFixtures.mcp),
    listWorkspaceContexts: async () =>
      structuredClone(capabilitySettingsFixtures.contexts),
    listSchedules: async () =>
      structuredClone(capabilitySettingsFixtures.schedules),
    listModels: async () => structuredClone(capabilitySettingsFixtures.models),
    getModelDefault: async () =>
      structuredClone(capabilitySettingsFixtures.modelDefault),
    getCapabilitySettings: async () =>
      structuredClone(capabilitySettingsFixtures.settings),
    getMemoryEntry: async (id: string) => ({
      ...structuredClone(
        capabilitySettingsFixtures.memory.find((entry) => entry.id === id)!,
      ),
      content:
        id === "host-guide" ? "private full shared memory" : "likes tabs",
    }),
    getManagedSkill: async (id: string) => ({
      ...structuredClone(
        capabilitySettingsFixtures.skills.find((skill) => skill.id === id)!,
      ),
      instructions:
        id === "host-reviewer"
          ? "private shared instructions"
          : "write concise notes",
    }),
    getMcpConfiguration: async (id: string) => ({
      ...structuredClone(
        capabilitySettingsFixtures.mcp.find((entry) => entry.id === id)!,
      ),
      url:
        id === "host-search"
          ? "https://private.example.invalid/secret"
          : "https://mcp.example.invalid",
    }),
    getWorkspaceContext: async (id: string) =>
      structuredClone(
        capabilitySettingsFixtures.contexts.find((entry) => entry.id === id)!,
      ),
    bindSessionContext: async (sessionId: string, contextId: string) => ({
      session_id: sessionId,
      context_id: contextId,
      name: contextId,
      workspace_label: "shared-docs",
      status: "read_only",
    }),
    ...overrides,
  } as unknown as ApiClient;
}
