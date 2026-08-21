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

export interface MemoryRecord {
  id: string;
  name: string;
  description?: string | null;
  snippet?: string | null;
  scope?: string | null;
  actions: readonly string[];
}

export interface MemoryDetail extends MemoryRecord {
  kind?: string | null;
  content: string;
  status?: string | null;
}

export interface MemorySettingsService {
  list(): Promise<readonly MemoryRecord[]>;
  get(id: string): Promise<MemoryDetail>;
  write(input: {
    name: string;
    kind: string;
    description: string;
    content: string;
  }): Promise<CapabilityActionResult>;
  remove(id: string): Promise<CapabilityActionResult>;
}

export function MemorySettings({
  service,
  canMutate,
  searchable = false,
}: {
  service: MemorySettingsService;
  canMutate: boolean;
  /** 083 FR-008: a client-side filter over listed metadata; off by default so Web is unchanged. */
  searchable?: boolean;
}) {
  const { t } = useTranslation();
  const [entries, setEntries] = useState<readonly MemoryRecord[] | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");
  const [content, setContent] = useState("");
  const [query, setQuery] = useState("");
  const [detail, setDetail] = useState<{
    title: string;
    fields: CapabilityDetailField[];
  } | null>(null);

  async function refresh() {
    try {
      setEntries(await service.list());
      setProblem(null);
    } catch {
      setEntries([]);
      setProblem(t("settings.memory.unavailable"));
    }
  }

  useEffect(() => {
    void refresh();
  }, [service]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    try {
      const result = await service.write({
        name,
        kind: "user",
        description: "",
        content,
      });
      if (!result.ok) {
        setProblem(result.message);
        return;
      }
      setName("");
      setContent("");
      await refresh();
    } catch {
      setProblem(t("settings.memory.unavailable"));
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    if (!window.confirm(t("settings.memory.deleteConfirm"))) return;
    setBusy(true);
    try {
      const result = await service.remove(id);
      if (!result.ok) {
        setProblem(result.message);
        return;
      }
      await refresh();
    } catch {
      setProblem(t("settings.memory.unavailable"));
    } finally {
      setBusy(false);
    }
  }

  async function open(entry: MemoryRecord) {
    try {
      const loaded = await service.get(entry.id);
      if (entry.scope === "shared_read_only") {
        setDetail({
          title: loaded.name,
          fields: [
            { label: t("settings.detail.kind"), value: loaded.kind },
            {
              label: t("settings.detail.description"),
              value: loaded.description,
            },
            { label: t("settings.detail.snippet"), value: loaded.snippet },
            { label: t("settings.detail.status"), value: loaded.status },
          ],
        });
        return;
      }
      setName(loaded.name);
      setContent(loaded.content);
    } catch {
      setProblem(t("settings.memory.detailsUnavailable"));
    }
  }

  const trimmedQuery = query.trim().toLowerCase();
  const visibleEntries =
    entries === null
      ? []
      : !searchable || !trimmedQuery
        ? entries
        : entries.filter((entry) =>
            [entry.name, entry.description ?? "", entry.snippet ?? ""].some(
              (value) => value.toLowerCase().includes(trimmedQuery),
            ),
          );

  return (
    <section className="capability-section" aria-labelledby="memory-settings-title">
      <div className="capability-section-heading">
        <h2 id="memory-settings-title">{t("settings.tab.memory")}</h2>
      </div>
      <form className="capability-form" onSubmit={(event) => void save(event)}>
        <label>
          <span>{t("settings.memory.name")}</span>
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            disabled={!canMutate || busy}
            required
          />
        </label>
        <label>
          <span>{t("settings.memory.content")}</span>
          <textarea
            value={content}
            onChange={(event) => setContent(event.target.value)}
            disabled={!canMutate || busy}
            required
          />
        </label>
        <button
          type="submit"
          className="primary"
          disabled={!canMutate || busy}
        >
          {t("settings.memory.save")}
        </button>
      </form>
      {problem && <div className="capability-problem">{problem}</div>}
      {searchable && (
        <label className="capability-search">
          <span>{t("settings.memory.search")}</span>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
      )}
      {entries === null ? (
        <div className="capability-loading">{t("settings.loading")}</div>
      ) : entries.length === 0 ? (
        <EmptySection message={t("settings.memory.empty")} />
      ) : visibleEntries.length === 0 ? (
        <EmptySection message={t("settings.memory.noMatches")} />
      ) : (
        <ul className="capability-list">
          {visibleEntries.map((entry) => (
            <li
              key={entry.id}
              className="capability-item"
              data-testid={`memory-${entry.id}`}
            >
              <div className="capability-item-copy">
                <strong>{entry.name}</strong>
                <span>{entry.description || entry.snippet}</span>
              </div>
              {entry.scope === "shared_read_only" && (
                <span className="settings-state">{t("settings.readOnly")}</span>
              )}
              <div className="capability-actions">
                {entry.actions.includes("open") && (
                  <button type="button" onClick={() => void open(entry)}>
                    {t("settings.action.open")}
                  </button>
                )}
                {entry.actions.includes("delete") && (
                  <button
                    type="button"
                    className="danger"
                    disabled={busy}
                    onClick={() => void remove(entry.id)}
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
          title={detail.title}
          fields={detail.fields}
          onClose={() => setDetail(null)}
        />
      )}
    </section>
  );
}
