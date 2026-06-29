import type { SessionSummary } from "../api/types";

const PREFERRED_MODEL_KEY = "loopplane.preferredModel";

interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): unknown;
  removeItem(key: string): unknown;
}

function defaultStorage(): StorageLike | null {
  return typeof window === "undefined" ? null : window.localStorage;
}

export function loadPreferredModel(storage: StorageLike | null = defaultStorage()) {
  return storage?.getItem(PREFERRED_MODEL_KEY) ?? null;
}

export function savePreferredModel(
  model: string | null,
  storage: StorageLike | null = defaultStorage(),
) {
  if (!storage) return;
  if (model) storage.setItem(PREFERRED_MODEL_KEY, model);
  else storage.removeItem(PREFERRED_MODEL_KEY);
}

export function chooseActiveAfterDelete(
  activeId: string | null,
  sessions: SessionSummary[],
  deletedIds: Set<string>,
): string | null {
  if (activeId && !deletedIds.has(activeId)) return activeId;
  return sessions.find((session) => !deletedIds.has(session.session_id))?.session_id ?? null;
}
