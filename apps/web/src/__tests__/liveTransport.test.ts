import { LiveSessionTransport } from "../api/liveTransport";

class FakeSocket {
  static instances: FakeSocket[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  sent: string[] = [];

  constructor(readonly url: string) {
    FakeSocket.instances.push(this);
  }

  send(data: string) {
    this.sent.push(data);
  }

  close() {}
}

describe("LiveSessionTransport", () => {
  beforeEach(() => {
    FakeSocket.instances = [];
  });

  it("opens with a ticket and yields ready plus event messages", async () => {
    const transport = new LiveSessionTransport({
      sessionId: "s1",
      ticket: "ticket-1",
      WebSocketImpl: FakeSocket as unknown as typeof WebSocket,
    });
    const stream = transport.streamSession("s1");
    const first = stream.next();
    const socket = FakeSocket.instances[0];

    expect(socket.url).toBe("/v1/sessions/s1/live?ticket=ticket-1");

    socket.onmessage?.(
      new MessageEvent("message", {
        data: JSON.stringify({ type: "ready", payload: { latest_sequence: 0 } }),
      }),
    );
    socket.onmessage?.(
      new MessageEvent("message", {
        data: JSON.stringify({
          type: "event",
          sequence: 1,
          payload: { type: "run-terminated" },
        }),
      }),
    );

    expect(await first).toEqual({ value: { type: "ready" }, done: false });
    expect(await stream.next()).toEqual({
      value: { type: "run-terminated" },
      done: false,
    });
  });

  it("sends submit options and abort messages over the live socket", async () => {
    const transport = new LiveSessionTransport({
      sessionId: "s1",
      ticket: "ticket-1",
      WebSocketImpl: FakeSocket as unknown as typeof WebSocket,
    });
    await transport.submit("s1", "hello", { permissionMode: "plan" });
    const socket = FakeSocket.instances[0];
    await transport.cancel("s1");

    expect(socket.sent.map((item) => JSON.parse(item))).toEqual([
      {
        type: "submit",
        payload: { prompt: "hello", permission_mode: "plan" },
      },
      { type: "abort", payload: {} },
    ]);
  });

  it("submits completed uploads through the structured live field", async () => {
    const transport = new LiveSessionTransport({
      sessionId: "s1",
      ticket: "ticket-1",
      WebSocketImpl: FakeSocket as unknown as typeof WebSocket,
    });

    await transport.submit("s1", "summarize", {
      uploads: [{ reference: "upload://notes" }],
    });

    expect(JSON.parse(FakeSocket.instances[0].sent[0])).toEqual({
      type: "submit",
      payload: {
        prompt: "summarize",
        uploads: [{ reference: "upload://notes" }],
      },
    });
  });

  it("preserves the existing live payload when no mode is selected", async () => {
    const transport = new LiveSessionTransport({
      sessionId: "s1",
      ticket: "ticket-1",
      WebSocketImpl: FakeSocket as unknown as typeof WebSocket,
    });

    await transport.submit("s1", "hello");

    expect(JSON.parse(FakeSocket.instances[0].sent[0])).toEqual({
      type: "submit",
      payload: { prompt: "hello" },
    });
  });
});
