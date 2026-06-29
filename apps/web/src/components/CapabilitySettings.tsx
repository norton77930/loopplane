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
  const [mcpName, setMcpName] = useState("");
  const [mcpUrl, setMcpUrl] = useState("");
  const [workspaceName, setWorkspaceName] = useState("");
  const [workspaceLabel, setWorkspaceLabel] = useState("");
  const [scheduleName, setScheduleName] = useState("");
  const [scheduleTrigger, setScheduleTrigger] = useState("");
  const [defaultModelId, setDefaultModelId] = useState("");

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

  function saveMcp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void client.upsertMcpConfiguration({
      name: mcpName,
      transport: "http",
      url: mcpUrl,
    });
  }

  function saveWorkspace(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void client.upsertWorkspaceContext({
      name: workspaceName,
      description: "",
      workspace_label: workspaceLabel,
    });
  }

  function saveSchedule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void client.upsertSchedule({
      name: scheduleName,
      description: "",
      trigger: scheduleTrigger,
      enabled: true,
    });
  }

  function saveModelDefault(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void client.setModelDefault(defaultModelId);
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
      <Section label="MCP" count={data?.mcp.length}>
        <form className="capability-form" onSubmit={saveMcp}>
          <input
            aria-label="mcp name"
            value={mcpName}
            onChange={(event) => setMcpName(event.target.value)}
          />
          <input
            aria-label="mcp url"
            value={mcpUrl}
            onChange={(event) => setMcpUrl(event.target.value)}
          />
          <button type="submit">Save MCP</button>
        </form>
      </Section>
      <Section label="Workspace" count={data?.contexts.length}>
        <form className="capability-form" onSubmit={saveWorkspace}>
          <input
            aria-label="workspace name"
            value={workspaceName}
            onChange={(event) => setWorkspaceName(event.target.value)}
          />
          <input
            aria-label="workspace label"
            value={workspaceLabel}
            onChange={(event) => setWorkspaceLabel(event.target.value)}
          />
          <button type="submit">Save workspace</button>
        </form>
      </Section>
      <Section label="Schedules" count={data?.schedules.length}>
        <form className="capability-form" onSubmit={saveSchedule}>
          <input
            aria-label="schedule name"
            value={scheduleName}
            onChange={(event) => setScheduleName(event.target.value)}
          />
          <input
            aria-label="schedule trigger"
            value={scheduleTrigger}
            onChange={(event) => setScheduleTrigger(event.target.value)}
          />
          <button type="submit">Save schedule</button>
        </form>
      </Section>
      <Section label="Model default" count={data ? 1 : undefined}>
        <form className="capability-form" onSubmit={saveModelDefault}>
          <input
            aria-label="default model id"
            value={defaultModelId}
            onChange={(event) => setDefaultModelId(event.target.value)}
          />
          <button type="submit">Save default model</button>
        </form>
      </Section>
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
