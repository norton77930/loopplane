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

function mcpAuthorization(value: unknown): McpRecord["authorization"] {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return undefined;
  }
  const raw = value as Record<string, unknown>;
  if (
    typeof raw.server !== "string" ||
    (raw.mode !== "none" && raw.mode !== "interactive") ||
    (raw.state !== "authorized" &&
      raw.state !== "needs_authorization" &&
      raw.state !== "failed")
  ) {
    return undefined;
  }
  return { server: raw.server, mode: raw.mode, state: raw.state };
}

function mcpRecord(value: unknown): McpRecord | null {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return null;
  const raw = value as Record<string, unknown>;
  if (typeof raw.id !== "string" || typeof raw.name !== "string") return null;
  return {
    id: raw.id,
    name: raw.name,
    transport: typeof raw.transport === "string" ? raw.transport : null,
    status: typeof raw.status === "string" ? raw.status : null,
    scope: typeof raw.scope === "string" ? raw.scope : null,
    actions: Array.isArray(raw.actions)
      ? raw.actions.filter((item): item is string => typeof item === "string")
      : [],
    authorization: mcpAuthorization(raw.authorization),
  };
}

export function createMcpSettingsService(
  bridge: CapabilityBridge,
): McpSettingsService {
  return {
    interactiveAuthorization: true,
    list: async () =>
      items<unknown>(await bridge.mcp.list())
        .map(mcpRecord)
        .filter((record): record is McpRecord => record !== null),
    get: async (id) => {
      const raw = await bridge.mcp.get(id);
      const projected = mcpRecord(raw);
      if (projected === null) return { name: "" };
      const detail = raw as Record<string, unknown>;
      return {
        ...projected,
        tools: Array.isArray(detail.tools)
          ? detail.tools.filter((item): item is string => typeof item === "string")
          : [],
        tool_count:
          typeof detail.tool_count === "number" ? detail.tool_count : 0,
      } satisfies McpDetail;
    },
    upsert: async (input) => opResult(await bridge.mcp.upsert(input)),
    reconnect: async (id) => opResult(await bridge.mcp.reconnect(id)),
    disconnect: async (id) => opResult(await bridge.mcp.disconnect(id)),
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
