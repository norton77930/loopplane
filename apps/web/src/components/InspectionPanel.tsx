import { useEffect, useState } from "react";

import type { ApiClient } from "../api/client";
import type {
  McpServerView,
  MemoryEntryView,
  SkillsResponse,
  ToolView,
} from "../api/types";

// A read-only, tabbed inspection panel (027): skills (+ load problems), registered tools,
// connected MCP servers (+ their tools), and memory (browse + search). Each tab fetches on view
// and shows a clear empty state. Metadata-only — no execute/edit affordance.
type Tab = "skills" | "tools" | "mcp" | "memory";

const TABS: { id: Tab; label: string }[] = [
  { id: "skills", label: "Skills" },
  { id: "tools", label: "Tools" },
  { id: "mcp", label: "MCP" },
  { id: "memory", label: "Memory" },
];

export function InspectionPanel({ client }: { client: ApiClient }) {
  const [tab, setTab] = useState<Tab>("skills");
  return (
    <aside className="inspection" data-testid="inspection">
      <div className="inspection-tabs" role="tablist">
        {TABS.map((entry) => (
          <button
            key={entry.id}
            type="button"
            role="tab"
            aria-selected={tab === entry.id}
            className={tab === entry.id ? "active" : ""}
            onClick={() => setTab(entry.id)}
          >
            {entry.label}
          </button>
        ))}
      </div>
      <div className="inspection-body">
        {tab === "skills" && <SkillsTab client={client} />}
        {tab === "tools" && <ToolsTab client={client} />}
        {tab === "mcp" && <McpTab client={client} />}
        {tab === "memory" && <MemoryTab client={client} />}
      </div>
    </aside>
  );
}

function Empty({ what }: { what: string }) {
  return <div className="inspection-empty">No {what} to show.</div>;
}

function SkillsTab({ client }: { client: ApiClient }) {
  const [data, setData] = useState<SkillsResponse | null>(null);
  useEffect(() => {
    let live = true;
    void client
      .inspectSkills()
      .then((result) => live && setData(result))
      .catch(() => live && setData({ skills: [], problems: [] }));
    return () => {
      live = false;
    };
  }, [client]);
  if (!data) return <div className="inspection-loading">Loading...</div>;
  if (data.skills.length === 0 && data.problems.length === 0) return <Empty what="skills" />;
  return (
    <ul className="inspection-list">
      {data.skills.map((skill) => (
        <li key={skill.name} className="inspection-item">
          <span className="item-name">{skill.name}</span>
          <span className="item-desc">{skill.description}</span>
          {skill.approval_required && <span className="badge">approval</span>}
        </li>
      ))}
      {data.problems.map((problem, index) => (
        <li key={`problem-${index}`} className="inspection-problem">
          {problem}
        </li>
      ))}
    </ul>
  );
}

function ToolsTab({ client }: { client: ApiClient }) {
  const [tools, setTools] = useState<ToolView[] | null>(null);
  useEffect(() => {
    let live = true;
    void client
      .inspectTools()
      .then((result) => live && setTools(result))
      .catch(() => live && setTools([]));
    return () => {
      live = false;
    };
  }, [client]);
  if (!tools) return <div className="inspection-loading">Loading...</div>;
  if (tools.length === 0) return <Empty what="tools" />;
  return (
    <ul className="inspection-list">
      {tools.map((tool) => (
        <li key={tool.name} className="inspection-item">
          <span className="item-name">{tool.name}</span>
          <span className="item-desc">{tool.description}</span>
          {tool.read_only && <span className="badge">read-only</span>}
        </li>
      ))}
    </ul>
  );
}

function McpTab({ client }: { client: ApiClient }) {
  const [servers, setServers] = useState<McpServerView[] | null>(null);
  useEffect(() => {
    let live = true;
    void client
      .inspectMcp()
      .then((result) => live && setServers(result))
      .catch(() => live && setServers([]));
    return () => {
      live = false;
    };
  }, [client]);
  if (!servers) return <div className="inspection-loading">Loading...</div>;
  if (servers.length === 0) return <Empty what="MCP servers" />;
  return (
    <ul className="inspection-list">
      {servers.map((server) => (
        <li key={server.name} className="inspection-item">
          <span className="item-name">{server.name}</span>
          <span className="item-desc">{server.tools.join(", ")}</span>
        </li>
      ))}
    </ul>
  );
}

function MemoryTab({ client }: { client: ApiClient }) {
  const [query, setQuery] = useState("");
  const [entries, setEntries] = useState<MemoryEntryView[] | null>(null);
  useEffect(() => {
    let live = true;
    void client
      .inspectMemory(query || undefined)
      .then((result) => live && setEntries(result))
      .catch(() => live && setEntries([]));
    return () => {
      live = false;
    };
  }, [client, query]);
  return (
    <div className="inspection-memory">
      <input
        type="text"
        aria-label="search memory"
        placeholder="Search memory..."
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      {entries === null ? (
        <div className="inspection-loading">Loading...</div>
      ) : entries.length === 0 ? (
        <Empty what="memory entries" />
      ) : (
        <ul className="inspection-list">
          {entries.map((entry) => (
            <li key={`${entry.type}-${entry.name}`} className="inspection-item">
              <span className="item-name">{entry.name}</span>
              <span className="item-meta">{entry.type}</span>
              <span className="item-desc">{entry.snippet}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
