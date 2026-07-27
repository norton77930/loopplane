import { ApiClient, createRestSessionTransport } from "../api/client";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("RestSessionTransport", () => {
  it("opens sessions through the existing REST endpoint", async () => {
    const urls: string[] = [];
    const fetchFn: typeof fetch = async (url) => {
      urls.push(String(url));
      return jsonResponse({ session_id: "s1" });
    };
    const transport = createRestSessionTransport(new ApiClient({ fetch: fetchFn }));

    await expect(transport.openSession("model-a")).resolves.toEqual({ session_id: "s1" });
    expect(urls).toEqual(["/v1/sessions?model=model-a"]);
  });

  it("submits an explicit per-run permission mode through REST", async () => {
    const requests: Array<{ url: string; body: string | undefined }> = [];
    const fetchFn: typeof fetch = async (url, init) => {
      requests.push({ url: String(url), body: init?.body as string | undefined });
      return jsonResponse({ accepted: true });
    };
    const transport = createRestSessionTransport(new ApiClient({ fetch: fetchFn }));

    await transport.submit("s1", "hello", { permissionMode: "plan" });

    expect(requests).toEqual([
      {
        url: "/v1/sessions/s1/submit",
        body: JSON.stringify({ prompt: "hello", permission_mode: "plan" }),
      },
    ]);
  });

  it("submits completed uploads through the structured REST field", async () => {
    const requests: string[] = [];
    const fetchFn: typeof fetch = async (_url, init) => {
      requests.push(init?.body as string);
      return jsonResponse({ accepted: true });
    };
    const transport = createRestSessionTransport(new ApiClient({ fetch: fetchFn }));

    await transport.submit("s1", "summarize", {
      uploads: [{ reference: "upload://notes" }],
    });

    expect(requests).toEqual([
      JSON.stringify({
        prompt: "summarize",
        uploads: [{ reference: "upload://notes" }],
      }),
    ]);
  });

  it("preserves the existing REST payload when no mode is selected", async () => {
    const requests: string[] = [];
    const fetchFn: typeof fetch = async (_url, init) => {
      requests.push(init?.body as string);
      return jsonResponse({ accepted: true });
    };
    const transport = createRestSessionTransport(new ApiClient({ fetch: fetchFn }));

    await transport.submit("s1", "hello");

    expect(requests).toEqual([JSON.stringify({ prompt: "hello" })]);
  });
});
