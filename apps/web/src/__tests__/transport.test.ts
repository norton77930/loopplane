import { ApiClient, createRestSessionTransport } from "../api/client";

describe("transport boundary", () => {
  it("creates the default REST/SSE transport through the API client seam", () => {
    const client = new ApiClient({ fetch: async () => new Response("{}") });
    const transport = createRestSessionTransport(client);

    expect(transport.mode).toBe("rest_sse");
  });
});
