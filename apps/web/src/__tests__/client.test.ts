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
