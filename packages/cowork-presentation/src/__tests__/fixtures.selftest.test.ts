import { describe, expect, it } from "vitest";

import { createPresentationHostFixture } from "./host-contract";
import { sampleProgressStream, SAMPLE_SESSION_ID } from "./events";

describe("T013 presentation fixtures", () => {
  it("hosts list sessions and capabilities", async () => {
    const host = createPresentationHostFixture();
    const sessions = await host.listSessions();
    expect(sessions).toHaveLength(1);
    const caps = await host.getCapabilities();
    expect(caps.some((c) => c.id === "memory" && c.available)).toBe(true);
    expect(host.calls).toContain("listSessions");
  });

  it("emits ordered sample progress sequences", () => {
    const events = sampleProgressStream(SAMPLE_SESSION_ID);
    expect(events.map((e) => e.sequence)).toEqual([1, 2, 3, 4]);
    expect(events.every((e) => e.session_id === SAMPLE_SESSION_ID)).toBe(true);
  });
});
