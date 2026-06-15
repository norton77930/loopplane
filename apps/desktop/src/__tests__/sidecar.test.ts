import { type DesktopBridge, SidecarTransport } from "../sidecar";

function fakeBridge(): {
  bridge: DesktopBridge;
  sent: string[];
  emit: (line: string) => void;
} {
  const sent: string[] = [];
  let handler: ((line: string) => void) | null = null;
  return {
    sent,
    emit: (line) => handler?.(line),
    bridge: {
      send: (line) => sent.push(line),
      onLine: (h) => {
        handler = h;
        return () => {
          handler = null;
        };
      },
    },
  };
}

describe("SidecarTransport", () => {
  it("sends a run request and yields events until the outcome", async () => {
    const { bridge, sent, emit } = fakeBridge();
    const transport = new SidecarTransport(bridge);
    const types: string[] = [];
    const done = (async () => {
      for await (const event of transport.run("hello")) types.push(event.type);
    })();
    emit(
      JSON.stringify({
        type: "assistant-output-increment",
        payload: { text: "hi", turn_index: 0 },
      }),
    );
    emit(JSON.stringify({ op: "outcome", reason: "natural-completion", turns: 1 }));
    await done;
    expect(types).toEqual(["assistant-output-increment"]);
    expect(JSON.parse(sent[0])).toEqual({ op: "run", prompt: "hello" });
  });

  it("answers approvals and questions over the bridge", () => {
    const { bridge, sent } = fakeBridge();
    const transport = new SidecarTransport(bridge);
    transport.answerApproval("r1", true);
    transport.answerQuestion("r2", ["yes"]);
    expect(JSON.parse(sent[0])).toEqual({ op: "approval", request_id: "r1", allow: true });
    expect(JSON.parse(sent[1])).toEqual({
      op: "question",
      request_id: "r2",
      answers: ["yes"],
    });
  });
});
