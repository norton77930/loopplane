/**
 * Sidecar-backed service adapters for the shared settings panels (083 Wave 4,
 * T024). Each adapter narrows the preload facade's `unknown` answers into the
 * shared service ports; a malformed answer degrades to an empty list or a
 * not-ok result rather than reaching the panels unchecked.
 */

import type {
  CapabilityActionResult,
  McpDetail,
  McpRecord,
  McpSettingsService,
  MemoryDetail,
  MemoryRecord,
  MemorySettingsService,
  ModelCatalogEntry,
  ModelDefaultSettingsService,
  ModelDefaultView,
  ScheduleDetail,
  ScheduleRecord,
  ScheduleSettingsService,
  SkillDetail,
  SkillRecord,
  SkillSettingsService,
  WorkspaceContextRecord,
  WorkspaceSettingsService,
} from "@loopplane/cowork-presentation";

type CapabilityBridge = NonNullable<
  typeof window.loopplaneDesktop
>["capabilityManagement"];

type GovernanceBridge = NonNullable<typeof window.loopplaneDesktop>["governance"];

function opResult(value: unknown): CapabilityActionResult {
  const record = value as { ok?: unknown; message?: unknown } | null;
  return {
    ok: record?.ok === true,
    message: typeof record?.message === "string" ? record.message : "",
  };
}

function items<T>(value: unknown): T[] {
  const list = (value as { items?: unknown } | null)?.items;
  return Array.isArray(list) ? (list as T[]) : [];
}

export function createMcpSettingsService(
  bridge: CapabilityBridge,
): McpSettingsService {
  return {
    list: async () => items<McpRecord>(await bridge.mcp.list()),
    get: async (id) => (await bridge.mcp.get(id)) as McpDetail,
    upsert: async (input) => opResult(await bridge.mcp.upsert(input)),
    reconnect: async (id) => opResult(await bridge.mcp.reconnect(id)),
    remove: async (id) => opResult(await bridge.mcp.remove(id)),
  };
}

export function createSkillSettingsService(
  bridge: CapabilityBridge,
): SkillSettingsService {
  return {
    list: async () => items<SkillRecord>(await bridge.skills.list()),
    get: async (id) => (await bridge.skills.get(id)) as SkillDetail,
    write: async (definition) => opResult(await bridge.skills.write(definition)),
    import: async (definition) =>
      opResult(await bridge.skills.import(definition)),
    remove: async (id) => opResult(await bridge.skills.remove(id)),
  };
}

export function createMemorySettingsService(
  bridge: CapabilityBridge,
): MemorySettingsService {
  return {
    list: async () => items<MemoryRecord>(await bridge.memory.list()),
    get: async (id) => (await bridge.memory.get(id)) as MemoryDetail,
    write: async (input) => opResult(await bridge.memory.write(input)),
    remove: async (id) => opResult(await bridge.memory.remove(id)),
  };
}

export function createScheduleSettingsService(
  bridge: GovernanceBridge,
): ScheduleSettingsService {
  return {
    list: async () => items<ScheduleRecord>(await bridge.schedules.list()),
    get: async (id) => (await bridge.schedules.get(id)) as ScheduleDetail,
    upsert: async (input) => opResult(await bridge.schedules.upsert(input)),
    runNow: async (id) => opResult(await bridge.schedules.runNow(id)),
    enable: async (id) => opResult(await bridge.schedules.enable(id)),
    disable: async (id) => opResult(await bridge.schedules.disable(id)),
    remove: async (id) => opResult(await bridge.schedules.remove(id)),
  };
}

export function createWorkspaceSettingsService(
  bridge: GovernanceBridge,
): WorkspaceSettingsService {
  return {
    list: async () =>
      items<WorkspaceContextRecord>(await bridge.contexts.list()),
    get: async (id) => (await bridge.contexts.get(id)) as WorkspaceContextRecord,
    upsert: async (input) => opResult(await bridge.contexts.upsert(input)),
    bind: (sessionId, contextId) => bridge.contexts.bind(sessionId, contextId),
    remove: async (id) => opResult(await bridge.contexts.remove(id)),
  };
}

export function createModelDefaultSettingsService(
  bridge: GovernanceBridge,
): ModelDefaultSettingsService {
  return {
    listModels: async () => {
      const raw = (await bridge.modelDefault.get()) as {
        models?: unknown;
      } | null;
      return Array.isArray(raw?.models)
        ? (raw.models as ModelCatalogEntry[])
        : [];
    },
    getDefault: async () => {
      const raw = (await bridge.modelDefault.get()) as {
        default?: unknown;
      } | null;
      const value = raw?.default;
      return value && typeof value === "object"
        ? (value as ModelDefaultView)
        : { status: "unavailable" };
    },
    setDefault: async (modelId) =>
      opResult(await bridge.modelDefault.set(modelId)),
    clearDefault: async () => opResult(await bridge.modelDefault.clear()),
  };
}
