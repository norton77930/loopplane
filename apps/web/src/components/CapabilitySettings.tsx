import { useEffect, useState } from "react";
import type { FormEvent, ReactNode } from "react";

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
  const [memoryName, setMemoryName] = useState("");
  const [memoryContent, setMemoryContent] = useState("");
  const [skillName, setSkillName] = useState("");
  const [skillInstructions, setSkillInstructions] = useState("");

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

  function saveMemory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void client.writeMemoryEntry({
      name: memoryName,
      kind: "user",
      description: "",
      content: memoryContent,
    });
  }

  function saveSkill(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void client.writeManagedSkill({
      name: skillName,
      description: "",
      instructions: skillInstructions,
    });
  }

  return (
    <div className="capability-settings">
      <Section label="Memory" count={data?.memory.length}>
        <form className="capability-form" onSubmit={saveMemory}>
          <input
            aria-label="memory name"
            value={memoryName}
            onChange={(event) => setMemoryName(event.target.value)}
          />
          <textarea
            aria-label="memory content"
            value={memoryContent}
            onChange={(event) => setMemoryContent(event.target.value)}
          />
          <button type="submit">Save memory</button>
        </form>
      </Section>
      <Section label="Skills" count={data?.skills.length}>
        <form className="capability-form" onSubmit={saveSkill}>
          <input
            aria-label="skill name"
            value={skillName}
            onChange={(event) => setSkillName(event.target.value)}
          />
          <textarea
            aria-label="skill instructions"
            value={skillInstructions}
            onChange={(event) => setSkillInstructions(event.target.value)}
          />
          <button type="submit">Save skill</button>
        </form>
      </Section>
      <Section label="MCP" count={data?.mcp.length} />
      <Section label="Workspace" count={data?.contexts.length} />
      <Section label="Schedules" count={data?.schedules.length} />
      <Section label="Model default" count={data ? 1 : undefined} />
    </div>
  );
}

function Section({
  label,
  count,
  children,
}: {
  label: string;
  count?: number;
  children?: ReactNode;
}) {
  return (
    <section className="capability-section">
      <h3>{label}</h3>
      <span className="item-meta">{count === undefined ? "Loading..." : `${count}`}</span>
      {children}
    </section>
  );
}
