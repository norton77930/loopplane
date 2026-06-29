import type { ApprovalDecision } from "./client";
import type { LiveClientMessage, LiveServerMessage, RawEvent } from "./types";
import type { SessionTransport, SubmitOptions } from "./transport";

export interface LiveSessionTransportOptions {
  sessionId: string;
  ticket: string;
  baseUrl?: string;
  lastSequence?: number;
  WebSocketImpl?: typeof WebSocket;
}

export class LiveSessionTransport implements SessionTransport {
  readonly mode = "live" as const;
  private socket?: WebSocket;
  private readonly WebSocketImpl: typeof WebSocket;
  private readonly queue: RawEvent[] = [];
  private readonly waiters: Array<(event: RawEvent) => void> = [];

  constructor(private readonly opts: LiveSessionTransportOptions) {
    this.WebSocketImpl = opts.WebSocketImpl ?? WebSocket;
  }

  async openSession(): Promise<{ session_id: string }> {
    return { session_id: this.opts.sessionId };
  }

  async *streamSession(sessionId: string): AsyncGenerator<RawEvent> {
    this.ensureSocket(sessionId);
    for (;;) {
      yield await this.nextEvent();
    }
  }

  async submit(sessionId: string, prompt: string, _options?: SubmitOptions): Promise<void> {
    this.send(sessionId, { type: "submit", payload: { prompt } });
  }

  async answerApproval(
    sessionId: string,
    requestId: string,
    decision: ApprovalDecision,
  ): Promise<void> {
    this.send(sessionId, {
      type: "approval_decision",
      payload: { request_id: requestId, ...decision },
    });
  }

  async answerQuestion(sessionId: string, requestId: string, answers: string[]): Promise<void> {
    this.send(sessionId, {
      type: "question_answer",
      payload: { request_id: requestId, answers },
    });
  }

  async cancel(sessionId: string): Promise<void> {
    this.send(sessionId, { type: "abort", payload: {} });
  }

  private ensureSocket(sessionId: string): WebSocket {
    if (this.socket) return this.socket;
    const params = new URLSearchParams({ ticket: this.opts.ticket });
    if (this.opts.lastSequence !== undefined) {
      params.set("last_sequence", String(this.opts.lastSequence));
    }
    const url = `${this.opts.baseUrl ?? ""}/v1/sessions/${encodeURIComponent(
      sessionId,
    )}/live?${params.toString()}`;
    const socket = new this.WebSocketImpl(url);
    socket.onmessage = (event) => this.handleMessage(String(event.data));
    this.socket = socket;
    return socket;
  }

  private send(sessionId: string, message: LiveClientMessage): void {
    this.ensureSocket(sessionId).send(JSON.stringify(message));
  }

  private handleMessage(raw: string): void {
    const message = JSON.parse(raw) as LiveServerMessage;
    if (message.type === "event" && message.payload) {
      this.enqueue(message.payload as RawEvent);
      return;
    }
    this.enqueue({ type: message.type });
  }

  private nextEvent(): Promise<RawEvent> {
    const queued = this.queue.shift();
    if (queued) return Promise.resolve(queued);
    return new Promise((resolve) => this.waiters.push(resolve));
  }

  private enqueue(event: RawEvent): void {
    const waiter = this.waiters.shift();
    if (waiter) {
      waiter(event);
      return;
    }
    this.queue.push(event);
  }
}
