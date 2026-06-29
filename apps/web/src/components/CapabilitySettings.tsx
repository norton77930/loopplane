import { useEffect, useState } from "react";

import type { ApiClient } from "../api/client";
import type {
  McpConfiguration,
  MemoryCapability,
  ManagedSchedule,
  ManagedSkill,
  ModelDefault,
  WorkspaceContext,
} from "../api/types";

interface CapabilityData {
  memory: MemoryCapability[];
  skills: ManagedSkill[];
  mcp: McpConfiguration[];
  contexts: WorkspaceContext[];
  schedules: ManagedSchedule[];
  modelDefault: ModelDefault;
}

const EMPTY_DEFAULT: ModelDefault = {
  model_id: null,
  label: null,
  status: "fallback",
  updated_at: null,
};

export function CapabilitySettings({ client }: { client: ApiClient }) {
  const [data, setData] = useState<CapabilityData | null>(null);

  useEffect(() => {
    let live = true;
    void Promise.all([
      client.listMemoryEntries(),
      client.listManagedSkills(),
      client.listMcpConfigurations(),
      client.listWorkspaceContexts(),
      client.listSchedules(),
      client.getModelDefault(),
    ])
      .then(([memory, skills, mcp, contexts, schedules, modelDefault]) => {
        if (live) setData({ memory, skills, mcp, contexts, schedules, modelDefault });
      })
      .catch(() => {
        if (live) {
          setData({
            memory: [],
            skills: [],
            mcp: [],
            contexts: [],
            schedules: [],
            modelDefault: EMPTY_DEFAULT,
          });
        }
      });
    return () => {
      live = false;
    };
  }, [client]);

  return (
    <div className="capability-settings">
      <Section label="Memory" count={data?.memory.length} />
      <Section label="Skills" count={data?.skills.length} />
      <Section label="MCP" count={data?.mcp.length} />
      <Section label="Workspace" count={data?.contexts.length} />
      <Section label="Schedules" count={data?.schedules.length} />
      <Section label="Model default" count={data ? 1 : undefined} />
    </div>
  );
}

function Section({ label, count }: { label: string; count?: number }) {
  return (
    <section className="capability-section">
      <h3>{label}</h3>
      <span className="item-meta">{count === undefined ? "Loading..." : `${count}`}</span>
    </section>
  );
}
