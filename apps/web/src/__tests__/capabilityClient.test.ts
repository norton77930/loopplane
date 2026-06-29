import { ApiClient } from "../api/client";

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    headers: { "content-type": "application/json" },
  });
}

describe("capability management client", () => {
  it("calls the foundation capability endpoints", async () => {
    const requests: Array<{ url: string; method?: string }> = [];
    const fetchFn: typeof fetch = async (url, init) => {
      requests.push({ url: String(url), method: init?.method });
      if (String(url).endsWith("/model-default")) {
        return jsonResponse({ model_id: null, label: null, status: "fallback" });
      }
      return jsonResponse([]);
    };
    const client = new ApiClient({ fetch: fetchFn });

    await client.listMemoryEntries();
    await client.listManagedSkills();
    await client.listMcpConfigurations();
    await client.listWorkspaceContexts();
    await client.listSchedules();
    await client.getModelDefault();

    expect(requests).toEqual([
      { url: "/v1/capabilities/memory", method: undefined },
      { url: "/v1/capabilities/skills", method: undefined },
      { url: "/v1/capabilities/mcp", method: undefined },
      { url: "/v1/capabilities/contexts", method: undefined },
      { url: "/v1/capabilities/schedules", method: undefined },
      { url: "/v1/capabilities/model-default", method: undefined },
    ]);
  });

  it("calls memory and skill mutation endpoints", async () => {
    const requests: Array<{ url: string; method?: string; body?: string }> = [];
    const fetchFn: typeof fetch = async (url, init) => {
      requests.push({
        url: String(url),
        method: init?.method,
        body: init?.body as string | undefined,
      });
      return jsonResponse({ result: { ok: true, resource_id: "item" } });
    };
    const client = new ApiClient({ fetch: fetchFn });

    await client.writeMemoryEntry({
      name: "pref",
      kind: "user",
      description: "editor preference",
      content: "likes tabs",
    });
    await client.deleteMemoryEntry("pref");
    await client.writeManagedSkill({
      name: "writer",
      description: "writes notes",
      instructions: "write concise notes",
    });
    await client.importManagedSkill({
      name: "reviewer",
      description: "reviews notes",
      instructions: "review concise notes",
    });
    await client.deleteManagedSkill("writer");

    expect(requests.map((request) => [request.url, request.method])).toEqual([
      ["/v1/capabilities/memory", "POST"],
      ["/v1/capabilities/memory/pref?confirm=true", "DELETE"],
      ["/v1/capabilities/skills", "POST"],
      ["/v1/capabilities/skills/import", "POST"],
      ["/v1/capabilities/skills/writer?confirm=true", "DELETE"],
    ]);
  });

  it("calls schedule and model-default mutation endpoints", async () => {
    const requests: Array<{ url: string; method?: string; body?: string }> = [];
    const fetchFn: typeof fetch = async (url, init) => {
      requests.push({
        url: String(url),
        method: init?.method,
        body: init?.body as string | undefined,
      });
      return jsonResponse({
        result: { ok: true, resource_id: "item" },
        schedule: { id: "daily-notes", name: "daily-notes", status: "enabled" },
        default: { model_id: "fast", label: "Fast model", status: "available" },
      });
    };
    const client = new ApiClient({ fetch: fetchFn });

    await client.upsertSchedule({
      name: "daily-notes",
      description: "refresh notes",
      trigger: "manual",
      enabled: true,
    });
    await client.runScheduleNow("daily-notes");
    await client.deleteSchedule("daily-notes");
    await client.setModelDefault("fast");

    expect(requests.map((request) => [request.url, request.method])).toEqual([
      ["/v1/capabilities/schedules", "POST"],
      ["/v1/capabilities/schedules/daily-notes/run-now", "POST"],
      ["/v1/capabilities/schedules/daily-notes?confirm=true", "DELETE"],
      ["/v1/capabilities/model-default", "POST"],
    ]);
  });
  it("calls MCP, workspace, and session-context endpoints", async () => {
    const requests: Array<{ url: string; method?: string; body?: string }> = [];
    const fetchFn: typeof fetch = async (url, init) => {
      requests.push({
        url: String(url),
        method: init?.method,
        body: init?.body as string | undefined,
      });
      return jsonResponse({
        result: { ok: true, resource_id: "item" },
        context: { id: "Docs", name: "Docs", workspace_label: "docs-repo" },
      });
    };
    const client = new ApiClient({ fetch: fetchFn });

    await client.upsertMcpConfiguration({
      name: "docs",
      transport: "http",
      url: "https://mcp.example.invalid",
    });
    await client.reconnectMcpConfiguration("docs");
    await client.deleteMcpConfiguration("docs");
    await client.upsertWorkspaceContext({
      name: "Docs",
      description: "documentation workspace",
      workspace_label: "docs-repo",
    });
    await client.deleteWorkspaceContext("Docs");
    await client.bindSessionContext("s1", "Docs");

    expect(requests.map((request) => [request.url, request.method])).toEqual([
      ["/v1/capabilities/mcp", "POST"],
      ["/v1/capabilities/mcp/docs/reconnect", "POST"],
      ["/v1/capabilities/mcp/docs?confirm=true", "DELETE"],
      ["/v1/capabilities/contexts", "POST"],
      ["/v1/capabilities/contexts/Docs?confirm=true", "DELETE"],
      ["/v1/sessions/s1/context", "POST"],
    ]);
  });
});
