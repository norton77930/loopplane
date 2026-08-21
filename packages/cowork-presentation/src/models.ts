/**
 * Transport-neutral presentation models (078 T061).
 */

export type PresentationCapabilityId =
  | "memory"
  | "skills"
  | "mcp"
  | "workspace"
  | "agent_controls"
  | "inspection"
  | string;

export type PresentationCapability = {
  id: PresentationCapabilityId;
  label: string;
  available: boolean;
  /** Host-approved action ids only; never generic tool dispatch. */
  actions: string[];
  /** Honest unavailable / private / unpriced markers. */
  status?: "available" | "unavailable" | "unknown" | "private_config";
};

export type PresentationSessionSummary = {
  id: string;
  title: string;
  starred: boolean;
  projectId: string | null;
};

/** Public display posture only; it intentionally cannot express a private value. */
export type PresentationAvailability =
  | "available"
  | "unavailable"
  | "unknown"
  | "read_only";

export type PresentationInspection = {
  sessionId: string | null;
  skills: Array<{ name: string; available: boolean }>;
  tools: Array<{ name: string; available: boolean }>;
  mcp: Array<{ name: string; available: boolean }>;
  memory: Array<{ source: string; snippet: string }>;
  /** Host-projected, public-safe inspection facets. */
  cost?: { status: "priced" | "unpriced" | "partially_unpriced" | "unavailable" | "unknown" };
  context?: { status: PresentationAvailability };
  uploads?: { status: PresentationAvailability };
  artifacts?: { status: PresentationAvailability };
  unavailable: boolean;
};

export type PresentationAgentControls = {
  sessionId: string;
  defaultMode: string | null;
  selectableModes: Array<{ id: string; kind: string; summary: string }>;
  activeRun: { mode: string; state: string; planActive: boolean } | null;
  lastAcceptedRun: { mode: string; state: string; planActive: boolean } | null;
  budget: {
    tracking: string;
    pricing: string;
    sessionGuard: string;
    monthlyGuard: string;
  };
  actions: string[];
  unavailable: boolean;
};

/** Capability map: which presentation domains are supported by an adapter. */
export const PRESENTATION_CAPABILITY_MAP = {
  sessions: true,
  interaction: true,
  inspection: true,
  agentControls: true,
  capabilities: true,
  settings: true,
  backup: false,
} as const;

export type PresentationCapabilityMap = typeof PRESENTATION_CAPABILITY_MAP;
