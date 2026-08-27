import { describe, expect, it, vi } from "vitest";

import { createMcpSettingsService } from "../services/capability-services";

describe("Desktop MCP authorization projection", () => {
  it("reconstructs exactly server/mode/state and drops value-like extras", async () => {
    const sentinel = "refresh-token-084-must-not-reach-renderer";
    const upsert = vi.fn(async () => ({ ok: true, message: "saved" }));
    const bridge = {
      mcp: {
        list: async () => ({
          items: [
            {
              id: "docs",
              name: "Docs",
              actions: ["reconnect"],
              authorization: {
                server: "docs",
                mode: "interactive",
                state: "needs_authorization",
                hint: sentinel,
                material: sentinel,
              },
            },
          ],
        }),
        get: async () => ({
          id: "docs",
          name: "Docs",
          actions: [],
          authorization: {
            server: "docs",
            mode: "interactive",
            state: "authorized",
            hint: sentinel,
          },
        }),
        upsert,
        reconnect: async () => ({ ok: true }),
        disconnect: async () => ({ ok: true }),
        remove: async () => ({ ok: true }),
      },
    } as unknown as Parameters<typeof createMcpSettingsService>[0];
    const service = createMcpSettingsService(bridge);

    const [listed] = await service.list();
    expect(listed?.authorization).toEqual({
      server: "docs",
      mode: "interactive",
      state: "needs_authorization",
    });
    expect(Object.keys(listed?.authorization ?? {})).toEqual([
      "server",
      "mode",
      "state",
    ]);
    expect(JSON.stringify(listed)).not.toContain(sentinel);

    await service.upsert({
      name: "docs",
      transport: "http",
      url: "https://mcp.example",
      mode: "interactive",
    });
    expect(upsert).toHaveBeenCalledWith(
      expect.objectContaining({ mode: "interactive" }),
    );
  });
});
