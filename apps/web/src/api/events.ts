// Parse the web API's SSE event stream into normalized event objects (R2).
// Each SSE frame's `data:` lines are a JSON-serialized normalized event.

import type { RawEvent } from "./types";

/** Parse one or more complete SSE frames (separated by a blank line). */
export function parseSSE(text: string): RawEvent[] {
  const events: RawEvent[] = [];
  for (const frame of text.split("\n\n")) {
    const data = frame
      .split("\n")
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).trim())
      .join("\n");
    if (!data) continue;
    try {
      events.push(JSON.parse(data) as RawEvent);
    } catch {
      // a malformed frame is skipped, never throws
    }
  }
  return events;
}

/** Read a fetch response body, yielding events as each SSE frame completes. */
export async function* streamEvents(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<RawEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let boundary = buffer.indexOf("\n\n");
    while (boundary >= 0) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      yield* parseSSE(frame);
      boundary = buffer.indexOf("\n\n");
    }
  }
  if (buffer.trim()) yield* parseSSE(buffer);
}
