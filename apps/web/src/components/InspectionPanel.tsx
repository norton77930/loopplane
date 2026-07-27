import { useEffect, useRef, useState, type KeyboardEvent } from "react";

import type { ApiClient } from "../api/client";
import type {
  McpServerView,
  MemoryEntryView,
  SkillsResponse,
  ToolView,
} from "../api/types";
import { useTranslation } from "../i18n/i18n";

// A read-only, tabbed inspection panel (027): skills (+ load problems), registered tools,
// connected MCP servers (+ their tools), and memory (browse + search). Each tab fetches on view
// and shows a clear empty state. Metadata-only — no execute/edit affordance.
type Tab = "skills" | "tools" | "mcp" | "memory";

const TABS: { id: Tab; labelKey: string }[] = [
  { id: "skills", labelKey: "inspection.tab.skills" },
  { id: "tools", labelKey: "inspection.tab.tools" },
  { id: "mcp", labelKey: "inspection.tab.mcp" },
  { id: "memory", labelKey: "inspection.tab.memory" },
];

export function InspectionPanel({ client }: { client: ApiClient }) {
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>("skills");
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  function selectAndFocus(index: number) {
    const entry = TABS[index];
    if (!entry) return;
    setTab(entry.id);
    tabRefs.current[index]?.focus();
  }

  function onTabKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    let nextIndex: number | undefined;
    if (event.key === "ArrowRight") nextIndex = (index + 1) % TABS.length;
    if (event.key === "ArrowLeft") nextIndex = (index - 1 + TABS.length) % TABS.length;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = TABS.length - 1;
    if (nextIndex === undefined) return;
    event.preventDefault();
    selectAndFocus(nextIndex);
  }

  return (
    <aside className="inspection" data-testid="inspection" aria-label={t("inspection.panel")}>
      <div className="inspection-tabs" role="tablist" aria-label={t("inspection.categories")}>
        {TABS.map((entry, index) => (
          <button
            key={entry.id}
            ref={(node) => {
              tabRefs.current[index] = node;
            }}
            id={`inspection-tab-${entry.id}`}
            type="button"
            role="tab"
            aria-selected={tab === entry.id}
            aria-controls={`inspection-panel-${entry.id}`}
            tabIndex={tab === entry.id ? 0 : -1}
            className={tab === entry.id ? "active" : ""}
            onClick={() => setTab(entry.id)}
            onKeyDown={(event) => onTabKeyDown(event, index)}
          >
            {t(entry.labelKey)}
          </button>
        ))}
      </div>
      <div
        id={`inspection-panel-${tab}`}
        className="inspection-body"
        role="tabpanel"
        aria-labelledby={`inspection-tab-${tab}`}
      >
        {tab === "skills" && <SkillsTab client={client} />}
        {tab === "tools" && <ToolsTab client={client} />}
        {tab === "mcp" && <McpTab client={client} />}
        {tab === "memory" && <MemoryTab client={client} />}
      </div>
    </aside>
  );
}

function Empty({ messageKey }: { messageKey: string }) {
  const { t } = useTranslation();
  return <div className="inspection-empty">{t(messageKey)}</div>;
}

function Loading({ messageKey }: { messageKey: string }) {
  const { t } = useTranslation();
  return (
    <div className="inspection-loading" role="status" aria-live="polite" aria-atomic="true">
      {t(messageKey)}
    </div>
  );
}

function ErrorState({ messageKey }: { messageKey: string }) {
  const { t } = useTranslation();
  return (
    <div className="inspection-error" role="alert">
      {t(messageKey)}
    </div>
  );
}

function SkillsTab({ client }: { client: ApiClient }) {
  const { t } = useTranslation();
  const [data, setData] = useState<SkillsResponse | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let live = true;
    void client
      .inspectSkills()
      .then((result) => {
        if (live) {
          setData(result);
          setFailed(false);
        }
      })
      .catch(() => {
        if (live) {
          setData(null);
          setFailed(true);
        }
      });
    return () => {
      live = false;
    };
  }, [client]);
  if (failed) return <ErrorState messageKey="inspection.skills.error" />;
  if (!data) return <Loading messageKey="inspection.skills.loading" />;
  if (data.skills.length === 0 && data.problems.length === 0)
    return <Empty messageKey="inspection.skills.empty" />;
  return (
    <ul className="inspection-list">
      {data.skills.map((skill) => (
        <li key={skill.name} className="inspection-item">
          <span className="item-name">{skill.name}</span>
          <span className="item-desc">{skill.description}</span>
          {skill.approval_required && <span className="badge">{t("inspection.approval")}</span>}
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
  const { t } = useTranslation();
  const [tools, setTools] = useState<ToolView[] | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let live = true;
    void client
      .inspectTools()
      .then((result) => {
        if (live) {
          setTools(result);
          setFailed(false);
        }
      })
      .catch(() => {
        if (live) {
          setTools(null);
          setFailed(true);
        }
      });
    return () => {
      live = false;
    };
  }, [client]);
  if (failed) return <ErrorState messageKey="inspection.tools.error" />;
  if (!tools) return <Loading messageKey="inspection.tools.loading" />;
  if (tools.length === 0) return <Empty messageKey="inspection.tools.empty" />;
  return (
    <ul className="inspection-list">
      {tools.map((tool) => (
        <li key={tool.name} className="inspection-item">
          <span className="item-name">{tool.name}</span>
          <span className="item-desc">{tool.description}</span>
          {tool.read_only && <span className="badge">{t("inspection.readOnly")}</span>}
        </li>
      ))}
    </ul>
  );
}

function McpTab({ client }: { client: ApiClient }) {
  const [servers, setServers] = useState<McpServerView[] | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let live = true;
    void client
      .inspectMcp()
      .then((result) => {
        if (live) {
          setServers(result);
          setFailed(false);
        }
      })
      .catch(() => {
        if (live) {
          setServers(null);
          setFailed(true);
        }
      });
    return () => {
      live = false;
    };
  }, [client]);
  if (failed) return <ErrorState messageKey="inspection.mcp.error" />;
  if (!servers) return <Loading messageKey="inspection.mcp.loading" />;
  if (servers.length === 0) return <Empty messageKey="inspection.mcp.empty" />;
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
  const { t } = useTranslation();
  const [query, setQuery] = useState("");
  const [entries, setEntries] = useState<MemoryEntryView[] | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let live = true;
    setEntries(null);
    setFailed(false);
    void client
      .inspectMemory(query || undefined)
      .then((result) => {
        if (live) {
          setEntries(result);
          setFailed(false);
        }
      })
      .catch(() => {
        if (live) {
          setEntries(null);
          setFailed(true);
        }
      });
    return () => {
      live = false;
    };
  }, [client, query]);
  return (
    <div className="inspection-memory">
      <input
        type="text"
        aria-label={t("inspection.searchMemory")}
        placeholder={t("inspection.searchMemoryPlaceholder")}
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      {failed ? (
        <ErrorState messageKey="inspection.memory.error" />
      ) : entries === null ? (
        <Loading messageKey="inspection.memory.loading" />
      ) : entries.length === 0 ? (
        <Empty messageKey="inspection.memory.empty" />
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
