import type { SessionSummary } from "../api/types";
import {
  chooseActiveAfterDelete,
  loadPreferredModel,
  savePreferredModel,
} from "../state/sessions";

const session = (id: string): SessionSummary => ({
  session_id: id,
  label: id,
  last_active_at: new Date().toISOString(),
  created_at: new Date().toISOString(),
});

describe("session parity state", () => {
  it("persists the preferred model for future draft chats", () => {
    const storage = new Map<string, string>();
    const store = {
      getItem: (key: string) => storage.get(key) ?? null,
      setItem: (key: string, value: string) => storage.set(key, value),
      removeItem: (key: string) => storage.delete(key),
    };

    savePreferredModel("model-a", store);
    expect(loadPreferredModel(store)).toBe("model-a");

    savePreferredModel(null, store);
    expect(loadPreferredModel(store)).toBeNull();
  });

  it("chooses a deterministic active-session fallback after bulk delete", () => {
    expect(
      chooseActiveAfterDelete("s1", [session("s1"), session("s2")], new Set(["s1"])),
    ).toBe("s2");
    expect(
      chooseActiveAfterDelete("s2", [session("s1"), session("s2")], new Set(["s1"])),
    ).toBe("s2");
    expect(chooseActiveAfterDelete("s1", [session("s1")], new Set(["s1"]))).toBeNull();
  });
});
