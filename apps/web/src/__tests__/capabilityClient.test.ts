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
});
