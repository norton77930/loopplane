import { ApiClient, ApiError } from "../api/client";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("ApiClient", () => {
  it("opens a session and carries the auth header", async () => {
    let seen: Headers | undefined;
    const fetchFn: typeof fetch = async (_url, init) => {
      seen = new Headers(init?.headers);
      return jsonResponse({ session_id: "s1" });
    };
    const client = new ApiClient({ authHeader: "Bearer t", fetch: fetchFn });
    expect(await client.openSession()).toEqual({ session_id: "s1" });
    expect(seen?.get("authorization")).toBe("Bearer t");
  });

  it("lists sessions", async () => {
    const fetchFn: typeof fetch = async () =>
      jsonResponse([{ session_id: "s1", last_active_at: "t" }]);
    const client = new ApiClient({ fetch: fetchFn });
    expect(await client.listSessions()).toHaveLength(1);
  });

  it("throws ApiError on an HTTP error", async () => {
    const fetchFn: typeof fetch = async () => new Response("", { status: 500 });
    const client = new ApiClient({ fetch: fetchFn });
    await expect(client.listSessions()).rejects.toBeInstanceOf(ApiError);
  });

  it("calls session parity endpoints", async () => {
    const requests: Array<{ url: string; method?: string; body?: string }> = [];
    const fetchFn: typeof fetch = async (url, init) => {
      requests.push({
        url: String(url),
        method: init?.method,
        body: init?.body as string | undefined,
      });
      if (String(url).includes("/fork")) return jsonResponse({ session_id: "fork" });
      if (String(url).includes("/bulk-delete")) {
        return jsonResponse({ deleted: ["s1"] });
      }
      return jsonResponse([]);
    };
    const client = new ApiClient({ fetch: fetchFn });

    await client.starSession("s1");
    await client.unstarSession("s1");
    await client.searchSessions("alpha");
    await expect(client.forkSession("s1", { sequence: 3 })).resolves.toEqual({
      session_id: "fork",
    });
    await expect(client.bulkDeleteSessions(["s1"])).resolves.toEqual({
      deleted: ["s1"],
    });

    expect(requests).toEqual([
      { url: "/v1/sessions/s1/star", method: "POST", body: undefined },
      { url: "/v1/sessions/s1/star", method: "DELETE", body: undefined },
      { url: "/v1/sessions/search?q=alpha", method: undefined, body: undefined },
      {
        url: "/v1/sessions/s1/fork",
        method: "POST",
        body: JSON.stringify({ sequence: 3 }),
      },
      {
        url: "/v1/sessions/bulk-delete",
        method: "POST",
        body: JSON.stringify({ session_ids: ["s1"], confirm: true }),
      },
    ]);
  });

  it("streams run events", async () => {
    const sse =
      'data: {"type":"assistant-output-increment","payload":{"text":"hi","turn_index":0}}\n\n' +
      'data: {"type":"run-terminated","payload":{"reason":"natural-completion","turns_taken":1}}\n\n';
    const fetchFn: typeof fetch = async () => new Response(sse, { status: 200 });
    const client = new ApiClient({ fetch: fetchFn });
    const types: string[] = [];
    for await (const event of client.streamRun("hi")) types.push(event.type);
    expect(types).toEqual(["assistant-output-increment", "run-terminated"]);
  });
});
