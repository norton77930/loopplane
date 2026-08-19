import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import { useTranslation } from "../../i18n/i18n";
import {
  CapabilityDetail,
  type CapabilityDetailField,
} from "./CapabilityDetail";
import { EmptySection } from "./EmptySection";

// Moved from apps/web in 083 Wave 3 behind a narrow service port (FR-020);
// apps/web adapts its HTTP client to this interface. Behavior is unchanged.

type NetworkMcpTransport = "http" | "sse" | "websocket";

export interface CapabilityActionResult {
  ok: boolean;
  message: string;
}

export interface McpRecord {
  id: string;
  name: string;
  transport?: string | null;
  status?: string | null;
  scope?: string | null;
  actions: readonly string[];
}

export interface McpDetail {
  name: string;
  transport?: string | null;
  status?: string | null;
  tools?: readonly string[];
  tool_count?: number;
  url?: string | null;
}

export interface McpSettingsService {
  list(): Promise<readonly McpRecord[]>;
  get(id: string): Promise<McpDetail>;
  upsert(input: {
    name: string;
    transport: NetworkMcpTransport;
    url: string;
  }): Promise<CapabilityActionResult>;
  reconnect(id: string): Promise<CapabilityActionResult>;
  remove(id: string): Promise<CapabilityActionResult>;
}

export function McpSettings({
  service,
  canMutate,
}: {
  service: McpSettingsService;
  canMutate: boolean;
}) {
  const { t } = useTranslation();
  const [configurations, setConfigurations] = useState<
    readonly McpRecord[] | null
  >(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");
  const [transport, setTransport] = useState<NetworkMcpTransport>("http");
  const [endpoint, setEndpoint] = useState("");
  const [detail, setDetail] = useState<{
    title: string;
    fields: CapabilityDetailField[];
  } | null>(null);

  async function refresh() {
    try {
      setConfigurations(await service.list());
      setProblem(null);
    } catch {
      setConfigurations([]);
      setProblem(t("settings.mcp.unavailable"));
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
        transport,
        url: endpoint,
      });
      if (!result.ok) {
        setProblem(result.message);
        return;
      }
      await refresh();
    } catch {
      setProblem(t("settings.mcp.unavailable"));
    } finally {
      setBusy(false);
    }
  }

  async function open(configuration: McpRecord) {
    try {
      const loaded = await service.get(configuration.id);
      if (configuration.scope === "shared_read_only") {
        setDetail({
          title: loaded.name,
          fields: [
            {
              label: t("settings.detail.transport"),
              value: loaded.transport,
            },
            { label: t("settings.detail.status"), value: loaded.status },
            {
              label: t("settings.detail.tools"),
              value: (loaded.tools ?? []).join(", "),
            },
            {
              label: t("settings.detail.toolCount"),
              value: loaded.tool_count,
            },
          ],
        });
        return;
      }
      setName(loaded.name);
      setTransport((loaded.transport as NetworkMcpTransport) ?? "http");
      setEndpoint(loaded.url ?? "");
    } catch {
      setProblem(t("settings.mcp.detailsUnavailable"));
    }
  }

  async function reconnect(id: string) {
    setBusy(true);
    try {
      const result = await service.reconnect(id);
      if (!result.ok) {
        setProblem(result.message);
        return;
      }
      await refresh();
    } catch {
      setProblem(t("settings.mcp.reconnectUnavailable"));
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    if (!window.confirm(t("settings.mcp.deleteConfirm"))) return;
    setBusy(true);
    try {
      const result = await service.remove(id);
      if (!result.ok) {
        setProblem(result.message);
        return;
      }
      await refresh();
    } catch {
      setProblem(t("settings.mcp.unavailable"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="capability-section" aria-labelledby="mcp-settings-title">
      <div className="capability-section-heading">
        <h2 id="mcp-settings-title">{t("settings.tab.mcp")}</h2>
      </div>
      <form className="capability-form" onSubmit={(event) => void save(event)}>
        <label>
          <span>{t("settings.mcp.name")}</span>
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            disabled={!canMutate || busy}
            required
          />
        </label>
        <label>
          <span>{t("settings.mcp.transport")}</span>
          <select
            value={transport}
            onChange={(event) =>
              setTransport(event.target.value as NetworkMcpTransport)
            }
            disabled={!canMutate || busy}
          >
            <option value="http">HTTP</option>
            <option value="sse">SSE</option>
            <option value="websocket">WebSocket</option>
          </select>
        </label>
        <label>
          <span>{t("settings.mcp.endpoint")}</span>
          <input
            type="url"
            value={endpoint}
            onChange={(event) => setEndpoint(event.target.value)}
            disabled={!canMutate || busy}
            required
          />
        </label>
        <button
          type="submit"
          className="primary"
          disabled={!canMutate || busy}
        >
          {t("settings.mcp.save")}
        </button>
      </form>
      {problem && <div className="capability-problem">{problem}</div>}
      {configurations === null ? (
        <div className="capability-loading">{t("settings.loading")}</div>
      ) : configurations.length === 0 ? (
        <EmptySection message={t("settings.mcp.empty")} />
      ) : (
        <ul className="capability-list">
          {configurations.map((configuration) => (
            <li
              key={configuration.id}
              className="capability-item"
              data-testid={"mcp-" + configuration.id}
            >
              <div className="capability-item-copy">
                <strong>{configuration.name}</strong>
                <span>
                  {[configuration.transport, configuration.status]
                    .filter(Boolean)
                    .join(" / ")}
                </span>
              </div>
              {configuration.scope === "shared_read_only" && (
                <span className="settings-state">{t("settings.readOnly")}</span>
              )}
              <div className="capability-actions">
                {configuration.actions.includes("open") && (
                  <button
                    type="button"
                    onClick={() => void open(configuration)}
                  >
                    {t("settings.action.open")}
                  </button>
                )}
                {configuration.actions.includes("reconnect") && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void reconnect(configuration.id)}
                  >
                    {t("settings.action.reconnect")}
                  </button>
                )}
                {configuration.actions.includes("delete") && (
                  <button
                    type="button"
                    className="danger"
                    disabled={busy}
                    onClick={() => void remove(configuration.id)}
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
