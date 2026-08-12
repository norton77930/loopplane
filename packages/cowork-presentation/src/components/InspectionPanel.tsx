import { useEffect, useRef, useState, type KeyboardEvent } from "react";

import { useTranslation } from "../i18n/i18n";
import type { PresentationInspection } from "../models";
import { inspectionStatusLabel } from "../inspection-status";

export type InspectionSkill = { name: string; description: string; approval_required: boolean };
export type InspectionTool = { name: string; description: string; read_only: boolean };
export type InspectionMcpServer = { name: string; tools: string[] };
export type InspectionMemoryEntry = { type: string; name: string; snippet: string };

export interface InspectionLoaders {
  inspectSkills(): Promise<{ skills: InspectionSkill[]; problems: string[] }>;
  inspectTools(): Promise<InspectionTool[]>;
  inspectMcp(): Promise<InspectionMcpServer[]>;
  inspectMemory(query?: string): Promise<InspectionMemoryEntry[]>;
}

type Tab = "skills" | "tools" | "mcp" | "memory";
const TABS: Array<{ id: Tab; labelKey: string }> = [
  { id: "skills", labelKey: "inspection.tab.skills" },
  { id: "tools", labelKey: "inspection.tab.tools" },
  { id: "mcp", labelKey: "inspection.tab.mcp" },
  { id: "memory", labelKey: "inspection.tab.memory" },
];

export function InspectionPanel({ loaders, inspection = null }: { loaders?: InspectionLoaders; inspection?: PresentationInspection | null }) {
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>("skills");
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  if (inspection || !loaders) {
    return <aside className="inspection" data-testid="inspection" aria-label={t("inspection.panel")}>
      {inspection?.unavailable || !inspection ? <p role="status">Inspection unavailable.</p> : <dl className="inspection-projection">
        <div><dt>Skills</dt><dd>{inspection.skills.length}</dd></div>
        <div><dt>Tools</dt><dd>{inspection.tools.length}</dd></div>
        <div><dt>MCP</dt><dd>{inspection.mcp.length}</dd></div>
        <div><dt>Cost</dt><dd>{inspectionStatusLabel(inspection.cost?.status)}</dd></div>
        <div><dt>Context</dt><dd>{inspectionStatusLabel(inspection.context?.status)}</dd></div>
        <div><dt>Uploads</dt><dd>{inspectionStatusLabel(inspection.uploads?.status)}</dd></div>
        <div><dt>Artifacts</dt><dd>{inspectionStatusLabel(inspection.artifacts?.status)}</dd></div>
      </dl>}
    </aside>;
  }

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

  return <aside className="inspection" data-testid="inspection" aria-label={t("inspection.panel")}>
    <div className="inspection-tabs" role="tablist" aria-label={t("inspection.categories")}>
      {TABS.map((entry, index) => <button key={entry.id} ref={(node) => { tabRefs.current[index] = node; }} id={`inspection-tab-${entry.id}`} type="button" role="tab" aria-selected={tab === entry.id} aria-controls={`inspection-panel-${entry.id}`} tabIndex={tab === entry.id ? 0 : -1} className={tab === entry.id ? "active" : ""} onClick={() => setTab(entry.id)} onKeyDown={(event) => onTabKeyDown(event, index)}>{t(entry.labelKey)}</button>)}
    </div>
    <div id={`inspection-panel-${tab}`} className="inspection-body" role="tabpanel" aria-labelledby={`inspection-tab-${tab}`}>
      {tab === "skills" ? <SkillsTab loaders={loaders} /> : null}
      {tab === "tools" ? <ToolsTab loaders={loaders} /> : null}
      {tab === "mcp" ? <McpTab loaders={loaders} /> : null}
      {tab === "memory" ? <MemoryTab loaders={loaders} /> : null}
    </div>
  </aside>;
}

function Empty({ messageKey }: { messageKey: string }) { const { t } = useTranslation(); return <div className="inspection-empty">{t(messageKey)}</div>; }
function Loading({ messageKey }: { messageKey: string }) { const { t } = useTranslation(); return <div className="inspection-loading" role="status" aria-live="polite" aria-atomic="true">{t(messageKey)}</div>; }
function ErrorState({ messageKey }: { messageKey: string }) { const { t } = useTranslation(); return <div className="inspection-error" role="alert">{t(messageKey)}</div>; }

function SkillsTab({ loaders }: { loaders: InspectionLoaders }) {
  const { t } = useTranslation(); const [data, setData] = useState<{ skills: InspectionSkill[]; problems: string[] } | null>(null); const [failed, setFailed] = useState(false);
  useEffect(() => { let live = true; void loaders.inspectSkills().then((result) => { if (live) { setData(result); setFailed(false); } }).catch(() => { if (live) { setData(null); setFailed(true); } }); return () => { live = false; }; }, [loaders]);
  if (failed) return <ErrorState messageKey="inspection.skills.error" />; if (!data) return <Loading messageKey="inspection.skills.loading" />; if (data.skills.length === 0 && data.problems.length === 0) return <Empty messageKey="inspection.skills.empty" />;
  return <ul className="inspection-list">{data.skills.map((skill) => <li key={skill.name} className="inspection-item"><span className="item-name">{skill.name}</span><span className="item-desc">{skill.description}</span>{skill.approval_required ? <span className="badge">{t("inspection.approval")}</span> : null}</li>)}{data.problems.map((problem, index) => <li key={`problem-${index}`} className="inspection-problem">{problem}</li>)}</ul>;
}
function ToolsTab({ loaders }: { loaders: InspectionLoaders }) {
  const { t } = useTranslation(); const [tools, setTools] = useState<InspectionTool[] | null>(null); const [failed, setFailed] = useState(false);
  useEffect(() => { let live = true; void loaders.inspectTools().then((result) => { if (live) { setTools(result); setFailed(false); } }).catch(() => { if (live) { setTools(null); setFailed(true); } }); return () => { live = false; }; }, [loaders]);
  if (failed) return <ErrorState messageKey="inspection.tools.error" />; if (!tools) return <Loading messageKey="inspection.tools.loading" />; if (tools.length === 0) return <Empty messageKey="inspection.tools.empty" />;
  return <ul className="inspection-list">{tools.map((tool) => <li key={tool.name} className="inspection-item"><span className="item-name">{tool.name}</span><span className="item-desc">{tool.description}</span>{tool.read_only ? <span className="badge">{t("inspection.readOnly")}</span> : null}</li>)}</ul>;
}
function McpTab({ loaders }: { loaders: InspectionLoaders }) {
  const [servers, setServers] = useState<InspectionMcpServer[] | null>(null); const [failed, setFailed] = useState(false);
  useEffect(() => { let live = true; void loaders.inspectMcp().then((result) => { if (live) { setServers(result); setFailed(false); } }).catch(() => { if (live) { setServers(null); setFailed(true); } }); return () => { live = false; }; }, [loaders]);
  if (failed) return <ErrorState messageKey="inspection.mcp.error" />; if (!servers) return <Loading messageKey="inspection.mcp.loading" />; if (servers.length === 0) return <Empty messageKey="inspection.mcp.empty" />;
  return <ul className="inspection-list">{servers.map((server) => <li key={server.name} className="inspection-item"><span className="item-name">{server.name}</span><span className="item-desc">{server.tools.join(", ")}</span></li>)}</ul>;
}
function MemoryTab({ loaders }: { loaders: InspectionLoaders }) {
  const { t } = useTranslation(); const [query, setQuery] = useState(""); const [entries, setEntries] = useState<InspectionMemoryEntry[] | null>(null); const [failed, setFailed] = useState(false);
  useEffect(() => { let live = true; setEntries(null); setFailed(false); void loaders.inspectMemory(query || undefined).then((result) => { if (live) { setEntries(result); setFailed(false); } }).catch(() => { if (live) { setEntries(null); setFailed(true); } }); return () => { live = false; }; }, [loaders, query]);
  return <div className="inspection-memory"><input type="text" aria-label={t("inspection.searchMemory")} placeholder={t("inspection.searchMemoryPlaceholder")} value={query} onChange={(event) => setQuery(event.target.value)} />{failed ? <ErrorState messageKey="inspection.memory.error" /> : entries === null ? <Loading messageKey="inspection.memory.loading" /> : entries.length === 0 ? <Empty messageKey="inspection.memory.empty" /> : <ul className="inspection-list">{entries.map((entry) => <li key={`${entry.type}-${entry.name}`} className="inspection-item"><span className="item-name">{entry.name}</span><span className="item-meta">{entry.type}</span><span className="item-desc">{entry.snippet}</span></li>)}</ul>}</div>;
}
