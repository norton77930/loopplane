import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import { useTranslation } from "../../i18n/i18n";
import {
  CapabilityDetail,
  type CapabilityDetailField,
} from "./CapabilityDetail";
import { EmptySection } from "./EmptySection";
import type { CapabilityActionResult } from "./McpSettings";

// Moved from apps/web in 083 Wave 3 behind a narrow service port (FR-020);
// apps/web adapts its HTTP client to this interface. Behavior is unchanged.

export interface WorkspaceContextRecord {
  id: string;
  name: string;
  workspace_label: string;
  description?: string | null;
  status?: string | null;
  scope?: string | null;
  actions: readonly string[];
}

export interface WorkspaceSettingsService {
  list(): Promise<readonly WorkspaceContextRecord[]>;
  get(id: string): Promise<WorkspaceContextRecord>;
  upsert(input: {
    name: string;
    description: string;
    workspace_label: string;
  }): Promise<CapabilityActionResult>;
  bind(sessionId: string, contextId: string): Promise<unknown>;
  remove(id: string): Promise<CapabilityActionResult>;
}

export function WorkspaceSettings({
  service,
  canMutate,
  sessionId,
  onContextBound,
}: {
  service: WorkspaceSettingsService;
  canMutate: boolean;
  sessionId?: string | null;
  onContextBound?: () => void | Promise<void>;
}) {
  const { t } = useTranslation();
  const [contexts, setContexts] = useState<
    readonly WorkspaceContextRecord[] | null
  >(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");
  const [workspaceLabel, setWorkspaceLabel] = useState("");
  const [detail, setDetail] = useState<{
    context: WorkspaceContextRecord;
    fields: CapabilityDetailField[];
  } | null>(null);

  async function refresh() {
    try {
      setContexts(await service.list());
      setProblem(null);
    } catch {
      setContexts([]);
      setProblem(t("settings.workspace.unavailable"));
    }
  }

  useEffect(() => {
    void refresh();
  }, [service]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    try {
      const result = await service.upsert({
        name,
        description: "",
        workspace_label: workspaceLabel,
      });
      if (!result.ok) {
        setProblem(result.message);
        return;
      }
      await refresh();
    } catch {
      setProblem(t("settings.workspace.unavailable"));
    } finally {
      setBusy(false);
    }
  }

  async function open(context: WorkspaceContextRecord) {
    try {
      const loaded = await service.get(context.id);
      if (context.scope === "shared_read_only") {
        setDetail({
          context: loaded,
          fields: [
            {
              label: t("settings.detail.description"),
              value: loaded.description,
            },
            {
              label: t("settings.detail.workspaceLabel"),
              value: loaded.workspace_label,
            },
            { label: t("settings.detail.status"), value: loaded.status },
          ],
        });
        return;
      }
      setName(loaded.name);
      setWorkspaceLabel(loaded.workspace_label);
    } catch {
      setProblem(t("settings.workspace.detailsUnavailable"));
    }
  }

  async function bind(id: string, closeDetail = false) {
    if (!sessionId) {
      setProblem(t("settings.workspace.sessionRequired"));
      return;
    }
    setBusy(true);
    try {
      await service.bind(sessionId, id);
      await onContextBound?.();
      await refresh();
      if (closeDetail) setDetail(null);
    } catch {
      setProblem(t("settings.workspace.bindingUnavailable"));
      if (closeDetail) setDetail(null);
      await refresh();
      setProblem(t("settings.workspace.bindingUnavailable"));
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    if (!window.confirm(t("settings.workspace.deleteConfirm"))) return;
    setBusy(true);
    try {
      const result = await service.remove(id);
      if (!result.ok) {
        setProblem(result.message);
        return;
      }
      await refresh();
    } catch {
      setProblem(t("settings.workspace.unavailable"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      className="capability-section"
      aria-labelledby="workspace-settings-title"
    >
      <div className="capability-section-heading">
        <h2 id="workspace-settings-title">
          {t("settings.tab.workspace")}
        </h2>
      </div>
      <form className="capability-form" onSubmit={(event) => void save(event)}>
        <label>
          <span>{t("settings.workspace.name")}</span>
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            disabled={!canMutate || busy}
            required
          />
        </label>
        <label>
          <span>{t("settings.workspace.label")}</span>
          <input
            value={workspaceLabel}
            onChange={(event) => setWorkspaceLabel(event.target.value)}
            disabled={!canMutate || busy}
            required
          />
        </label>
        <button
          type="submit"
          className="primary"
          disabled={!canMutate || busy}
        >
          {t("settings.workspace.save")}
        </button>
      </form>
      {problem && <div className="capability-problem">{problem}</div>}
      {contexts === null ? (
        <div className="capability-loading">{t("settings.loading")}</div>
      ) : contexts.length === 0 ? (
        <EmptySection message={t("settings.workspace.empty")} />
      ) : (
        <ul className="capability-list">
          {contexts.map((context) => (
            <li
              key={context.id}
              className="capability-item"
              data-testid={"context-" + context.id}
            >
              <div className="capability-item-copy">
                <strong>{context.name}</strong>
                <span>{context.workspace_label}</span>
              </div>
              {context.scope === "shared_read_only" && (
                <span className="settings-state">{t("settings.readOnly")}</span>
              )}
              <div className="capability-actions">
                {context.actions.includes("open") && (
                  <button type="button" onClick={() => void open(context)}>
                    {t("settings.action.open")}
                  </button>
                )}
                {context.actions.includes("bind") && (
                  <button
                    type="button"
                    disabled={busy || !sessionId}
                    onClick={() => void bind(context.id)}
                  >
                    {t("settings.action.bind")}
                  </button>
                )}
                {context.actions.includes("delete") && (
                  <button
                    type="button"
                    className="danger"
                    disabled={busy}
                    onClick={() => void remove(context.id)}
                  >
                    {t("settings.action.delete")}
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
      {detail && (
        <CapabilityDetail
          title={detail.context.name}
          fields={detail.fields}
          actions={
            detail.context.actions.includes("bind") ? (
              <button
                type="button"
                className="primary"
                disabled={busy || !sessionId}
                onClick={() => void bind(detail.context.id, true)}
              >
                {t("settings.action.bind")}
              </button>
            ) : undefined
          }
          onClose={() => setDetail(null)}
        />
      )}
    </section>
  );
}
