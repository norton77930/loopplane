/**
 * CoworkPresentationHost — transport-neutral presentation interface (078 T061).
 *
 * Web and Desktop adapters implement this; presentation never owns enforcement.
 */

import type {
  PresentationAgentControls,
  PresentationCapability,
  PresentationCapabilityMap,
  PresentationInspection,
  PresentationSessionSummary,
} from "./models";
import { PRESENTATION_CAPABILITY_MAP } from "./models";

export type ProgressHandler = (event: { type: string; payload?: unknown }) => void;

/** One-run presentation draft; acceptance remains host-owned. */
export type PresentationSubmitOptions = { permissionMode?: string };

export interface CoworkPresentationHost {
  /** Adapter capability map (honest unavailable flags). */
  capabilities(): PresentationCapabilityMap;

  listSessions(): Promise<PresentationSessionSummary[]>;

  getCapabilities(): Promise<PresentationCapability[]>;

  /** Invoke one allowlisted capability action; unsupported → rejected. */
  invokeCapabilityAction(
    capabilityId: string,
    action: string,
  ): Promise<PresentationCapability[]>;

  getInspection(sessionId: string | null): Promise<PresentationInspection>;

  getAgentControls(sessionId: string): Promise<PresentationAgentControls>;

  subscribeProgress(
    sessionId: string,
    onEvent: ProgressHandler,
  ): () => void;

  submit(
    sessionId: string,
    prompt: string,
    options?: PresentationSubmitOptions,
  ): Promise<void>;

  answerApproval(requestId: string, allow: boolean): Promise<void>;

  answerQuestion(requestId: string, answers: string[]): Promise<void>;

  cancel(sessionId: string): Promise<void>;
}

export function defaultCapabilityMap(): PresentationCapabilityMap {
  return { ...PRESENTATION_CAPABILITY_MAP };
}

/** Type guard for allowlisted capability actions in presentation layer. */
export function isAllowlistedCapabilityAction(
  capabilityId: string,
  action: string,
  capabilities: PresentationCapability[],
): boolean {
  const cap = capabilities.find((c) => c.id === capabilityId);
  if (!cap || !cap.available) return false;
  return cap.actions.includes(action);
}
