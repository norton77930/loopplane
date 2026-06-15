// The desktop renderer transport over the local sidecar bridge (feature 019).
// Mirrors unit 018's HTTP client, but speaks line-delimited JSON over window.api
// (Electron IPC) instead of HTTP. Reuses 018's RawEvent type.

import type { RawEvent } from "@web/api/types";

/** What the preload exposes as window.api: a line channel to the sidecar. */
export interface DesktopBridge {
  send(line: string): void;
  onLine(handler: (line: string) => void): () => void;
}

interface ControlLine {
  op: "outcome" | "error";
}

export class SidecarTransport {
  constructor(private readonly bridge: DesktopBridge) {}

  async *run(prompt: string): AsyncGenerator<RawEvent> {
    const queue: string[] = [];
    let wake: (() => void) | null = null;
    const unsubscribe = this.bridge.onLine((line) => {
      queue.push(line);
      wake?.();
      wake = null;
    });
    this.bridge.send(JSON.stringify({ op: "run", prompt }));
    try {
      for (;;) {
        if (queue.length === 0) {
          await new Promise<void>((resolve) => {
            wake = resolve;
          });
        }
        const line = queue.shift();
        if (line === undefined) continue;
        const parsed = JSON.parse(line) as RawEvent | ControlLine;
        if ("op" in parsed) return; // outcome / error ends the run
        yield parsed;
      }
    } finally {
      unsubscribe();
    }
  }

  answerApproval(requestId: string, allow: boolean): void {
    this.bridge.send(
      JSON.stringify({ op: "approval", request_id: requestId, allow }),
    );
  }

  answerQuestion(requestId: string, answers: string[]): void {
    this.bridge.send(
      JSON.stringify({ op: "question", request_id: requestId, answers }),
    );
  }
}
