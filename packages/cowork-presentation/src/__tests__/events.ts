/**
 * Normalized runtime-event samples for shared presentation tests (078 T013).
 * Shapes mirror loopplane.events serialize_event JSON (SCHEMA_VERSION stable).
 */

export type NormalizedEventSample = {
  type: string;
  session_id: string;
  sequence: number;
  [key: string]: unknown;
};

export const SAMPLE_SESSION_ID = "sess-synth-001";

export function textDelta(
  sequence: number,
  text: string,
  sessionId = SAMPLE_SESSION_ID,
): NormalizedEventSample {
  return {
    type: "text_delta",
    session_id: sessionId,
    sequence,
    text,
  };
}

export function toolCallStarted(
  sequence: number,
  toolName: string,
  callId = "call-1",
  sessionId = SAMPLE_SESSION_ID,
): NormalizedEventSample {
  return {
    type: "tool_call_started",
    session_id: sessionId,
    sequence,
    call_id: callId,
    tool_name: toolName,
  };
}

export function approvalRequested(
  sequence: number,
  requestId = "appr-1",
  sessionId = SAMPLE_SESSION_ID,
): NormalizedEventSample {
  return {
    type: "approval_requested",
    session_id: sessionId,
    sequence,
    request_id: requestId,
    summary: "Allow tool use",
  };
}

export function questionAsked(
  sequence: number,
  questionId = "q-1",
  sessionId = SAMPLE_SESSION_ID,
): NormalizedEventSample {
  return {
    type: "question_asked",
    session_id: sessionId,
    sequence,
    question_id: questionId,
    prompt: "Which option?",
    options: ["A", "B"],
  };
}

export function turnEnded(
  sequence: number,
  sessionId = SAMPLE_SESSION_ID,
): NormalizedEventSample {
  return {
    type: "turn_ended",
    session_id: sessionId,
    sequence,
    termination_reason: "completed",
  };
}

/** Ordered progress stream for multi-pane / adapter tests. */
export function sampleProgressStream(
  sessionId = SAMPLE_SESSION_ID,
): NormalizedEventSample[] {
  return [
    textDelta(1, "Hello", sessionId),
    toolCallStarted(2, "read_file", "c1", sessionId),
    textDelta(3, " world", sessionId),
    turnEnded(4, sessionId),
  ];
}
