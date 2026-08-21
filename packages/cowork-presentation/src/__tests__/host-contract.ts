/**
 * CoworkPresentationHost contract fixtures (078 T013).
 * Transport-neutral host surface used by Web and Desktop adapters.
 */

import type { NormalizedEventSample } from "./events";

export type HostCapability = {
  id: string;
  label: string;
  available: boolean;
  actions: string[];
};

export type HostSessionSummary = {
  id: string;
  title: string;
  starred: boolean;
  projectId: string | null;
};

export type CoworkPresentationHostFixture = {
  listSessions: () => Promise<HostSessionSummary[]>;
  getCapabilities: () => Promise<HostCapability[]>;
  subscribeProgress: (
    sessionId: string,
    onEvent: (event: NormalizedEventSample) => void,
  ) => () => void;
  submit: (sessionId: string, prompt: string) => Promise<void>;
  answerApproval: (requestId: string, allow: boolean) => Promise<void>;
  answerQuestion: (questionId: string, answer: string) => Promise<void>;
  cancel: (sessionId: string) => Promise<void>;
  /** Test instrumentation */
  calls: string[];
};

export function createPresentationHostFixture(
  overrides: Partial<CoworkPresentationHostFixture> = {},
): CoworkPresentationHostFixture {
  const calls: string[] = [];
  const base: CoworkPresentationHostFixture = {
    calls,
    async listSessions() {
      calls.push("listSessions");
      return [
        {
          id: "sess-1",
          title: "Demo",
          starred: false,
          projectId: null,
        },
      ];
    },
    async getCapabilities() {
      calls.push("getCapabilities");
      return [
        {
          id: "memory",
          label: "Memory",
          available: true,
          actions: ["refresh"],
        },
        {
          id: "mcp",
          label: "MCP",
          available: false,
          actions: [],
        },
      ];
    },
    subscribeProgress(sessionId, onEvent) {
      calls.push(`subscribeProgress:${sessionId}`);
      void onEvent;
      return () => {
        calls.push(`unsubscribeProgress:${sessionId}`);
      };
    },
    async submit(sessionId, prompt) {
      calls.push(`submit:${sessionId}:${prompt}`);
    },
    async answerApproval(requestId, allow) {
      calls.push(`answerApproval:${requestId}:${allow}`);
    },
    async answerQuestion(questionId, answer) {
      calls.push(`answerQuestion:${questionId}:${answer}`);
    },
    async cancel(sessionId) {
      calls.push(`cancel:${sessionId}`);
    },
  };
  return { ...base, ...overrides, calls };
}
