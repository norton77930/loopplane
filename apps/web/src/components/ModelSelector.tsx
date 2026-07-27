import { useEffect, useState } from "react";

import type { ApiClient } from "../api/client";
import type { ModelInfo } from "../api/types";

// The session's model selector (028, FR-002): lists the host's model catalog and reports the
// chosen id. Hides gracefully when no catalog is configured (edge case).
interface Props {
  client: ApiClient;
  value: string | null;
  onChange: (model: string | null) => void;
  scope?: "current" | "next";
}

export function ModelSelector({ client, value, onChange, scope = "current" }: Props) {
  const [models, setModels] = useState<ModelInfo[]>([]);
  useEffect(() => {
    let live = true;
    void client
      .listModels()
      .then((result) => live && setModels(result))
      .catch(() => live && setModels([]));
    return () => {
      live = false;
    };
  }, [client]);

  if (models.length === 0) return null;
  return (
    <select
      className="model-selector"
      aria-label={scope === "next" ? "Next chat model" : "model"}
      value={value ?? ""}
      onChange={(event) => onChange(event.target.value || null)}
    >
      <option value="">Default model</option>
      {models.map((model) => (
        <option key={model.id} value={model.id}>
          {model.label}
        </option>
      ))}
    </select>
  );
}
