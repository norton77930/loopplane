import { parseSSE, streamEvents } from "../api/events";

function streamOf(chunks: string[]): ReadableStream<Uint8Array> {
  const enc = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(enc.encode(chunk));
      controller.close();
    },
  });
}

describe("parseSSE", () => {
  it("parses data frames into events", () => {
    const text =
      'data: {"type":"assistant-output-increment","payload":{"text":"hi","turn_index":0}}\n\n' +
      'data: {"type":"run-terminated","payload":{"reason":"natural-completion","turns_taken":1}}\n\n';
    const events = parseSSE(text);
    expect(events).toHaveLength(2);
    expect(events[0].type).toBe("assistant-output-increment");
    expect(events[1].type).toBe("run-terminated");
  });

  it("skips a malformed frame without throwing", () => {
    expect(parseSSE("data: not json\n\n")).toHaveLength(0);
  });
});

describe("streamEvents", () => {
  it("yields events across chunk boundaries", async () => {
    const stream = streamOf([
      'data: {"type":"tool-call-started","pay',
      'load":{"call_id":"c1","tool_name":"echo"}}\n\n',
      'data: {"type":"run-terminated","payload":{"reason":"natural-completion","turns_taken":1}}\n\n',
    ]);
    const types: string[] = [];
    for await (const event of streamEvents(stream)) types.push(event.type);
    expect(types).toEqual(["tool-call-started", "run-terminated"]);
  });
});
