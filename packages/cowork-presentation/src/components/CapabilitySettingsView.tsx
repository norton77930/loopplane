import { useRef, useState, type KeyboardEvent, type ReactNode } from "react";

import type { PresentationCapability } from "../models";

export interface CapabilitySettingsTab { id: string; label: string; }
export interface CapabilitySettingsViewProps {
  title: string;
  categoriesLabel: string;
  backLabel: string;
  tabs: CapabilitySettingsTab[];
  initialTabId?: string;
  status?: ReactNode;
  /** Host-projected settings availability; absent means the adapter has no projection. */
  capabilities?: PresentationCapability[] | null;
  onCapabilityAction?: (capabilityId: string, action: string) => void | Promise<void>;
  onBack?: () => void;
  renderTab: (id: string) => ReactNode;
}

/** Generic settings workspace. Host adapters supply data/actions and rendered tab content. */
export function CapabilitySettingsView({ title, categoriesLabel, backLabel, tabs, initialTabId, status, capabilities, onCapabilityAction, onBack, renderTab }: CapabilitySettingsViewProps) {
  const [activeId, setActiveId] = useState(initialTabId ?? tabs[0]?.id ?? "");
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const active = tabs.find((tab) => tab.id === activeId) ?? tabs[0];
  function selectAndFocus(index: number) { const tab = tabs[index]; if (!tab) return; setActiveId(tab.id); tabRefs.current[index]?.focus(); }
  function onTabKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    let nextIndex: number | undefined;
    if (event.key === "ArrowDown") nextIndex = (index + 1) % tabs.length;
    if (event.key === "ArrowUp") nextIndex = (index - 1 + tabs.length) % tabs.length;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = tabs.length - 1;
    if (nextIndex === undefined) return;
    event.preventDefault(); selectAndFocus(nextIndex);
  }
  if (!active) return null;
  return <main className="capability-settings"><header className="capability-settings-header">{onBack ? <button type="button" className="settings-back" onClick={onBack}><span aria-hidden="true">←</span><span>{backLabel}</span></button> : null}<div className="settings-title-group"><h1>{title}</h1>{status}</div></header>{capabilities === null ? <p className="settings-state" role="status">Capability status unavailable.</p> : Array.isArray(capabilities) ? <dl className="capability-settings-status" aria-label="Capability status">{capabilities.map((capability) => <div key={capability.id}><dt>{capability.label}</dt><dd>{capability.available ? capability.status === "private_config" ? "unavailable" : capability.status ?? "available" : "unavailable"}{capability.available && onCapabilityAction ? capability.actions.map((action) => <button key={action} type="button" onClick={() => void onCapabilityAction(capability.id, action)}>{action}</button>) : null}</dd></div>)}</dl> : null}<div className="capability-settings-workspace"><div className="capability-settings-tabs" role="tablist" aria-label={categoriesLabel} aria-orientation="vertical">{tabs.map((tab, index) => <button key={tab.id} ref={(node) => { tabRefs.current[index] = node; }} id={`settings-tab-${tab.id}`} type="button" role="tab" aria-selected={activeId === tab.id} aria-controls={`settings-panel-${tab.id}`} tabIndex={activeId === tab.id ? 0 : -1} className={activeId === tab.id ? "active" : ""} onClick={() => setActiveId(tab.id)} onKeyDown={(event) => onTabKeyDown(event, index)}>{tab.label}</button>)}</div><div id={`settings-panel-${active.id}`} className="capability-settings-body" role="tabpanel" aria-labelledby={`settings-tab-${active.id}`}>{renderTab(active.id)}</div></div></main>;
}
