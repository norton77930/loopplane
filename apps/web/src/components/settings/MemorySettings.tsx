import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import type { ApiClient } from "../../api/client";
import type { MemoryCapability } from "../../api/types";
import { useTranslation } from "../../i18n/i18n";
import {
  CapabilityDetail,
  type CapabilityDetailField,
} from "./CapabilityDetail";
import { EmptySection } from "./EmptySection";

export function MemorySettings({
  client,
  canMutate,
}: {
  client: ApiClient;
  canMutate: boolean;
}) {
  const { t } = useTranslation();
  const [entries, setEntries] = useState<MemoryCapability[] | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");
  const [content, setContent] = useState("");
  const [detail, setDetail] = useState<{
    title: string;
    fields: CapabilityDetailField[];
  } | null>(null);

  async function refresh() {
    try {
      setEntries(await client.listMemoryEntries());
      setProblem(null);
    } catch {
      setEntries([]);
      setProblem(t("settings.memory.unavailable"));
    }
  }

  useEffect(() => {
    void refresh();
  }, [client]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    try {
      const response = await client.writeMemoryEntry({
        name,
        kind: "user",
        description: "",
        content,
      });
      if (!response.result.ok) {
        setProblem(response.result.message);
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
      const result = await client.deleteMemoryEntry(id);
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

  async function open(entry: MemoryCapability) {
    try {
      const loaded = await client.getMemoryEntry(entry.id);
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
      {entries === null ? (
        <div className="capability-loading">{t("settings.loading")}</div>
      ) : entries.length === 0 ? (
        <EmptySection message={t("settings.memory.empty")} />
      ) : (
        <ul className="capability-list">
          {entries.map((entry) => (
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
