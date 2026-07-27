import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import type { ApiClient } from "../../api/client";
import type { ModelDefault, ModelInfo } from "../../api/types";
import { useTranslation } from "../../i18n/i18n";
import { EmptySection } from "./EmptySection";

export function ModelDefaultSettings({
  client,
  canMutate,
}: {
  client: ApiClient;
  canMutate: boolean;
}) {
  const { t } = useTranslation();
  const [models, setModels] = useState<ModelInfo[] | null>(null);
  const [current, setCurrent] = useState<ModelDefault | null>(null);
  const [selected, setSelected] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function refreshDefault() {
    try {
      const next = await client.getModelDefault();
      setCurrent(next);
      setSelected(next.status === "available" ? (next.model_id ?? "") : "");
      setProblem(null);
    } catch {
      setCurrent(null);
      setProblem(t("settings.model.unavailable"));
    }
  }

  useEffect(() => {
    let live = true;
    void Promise.all([client.listModels(), client.getModelDefault()])
      .then(([catalog, next]) => {
        if (!live) return;
        setModels(catalog);
        setCurrent(next);
        setSelected(next.status === "available" ? (next.model_id ?? "") : "");
        setProblem(null);
      })
      .catch(() => {
        if (!live) return;
        setModels([]);
        setCurrent(null);
        setProblem(t("settings.model.unavailable"));
      });
    return () => {
      live = false;
    };
  }, [client]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) return;
    setBusy(true);
    try {
      const response = await client.setModelDefault(selected);
      if (!response.result.ok) {
        setProblem(response.result.message);
        return;
      }
      await refreshDefault();
    } catch {
      setProblem(t("settings.model.unavailable"));
    } finally {
      setBusy(false);
    }
  }

  async function clear() {
    setBusy(true);
    try {
      const response = await client.clearModelDefault();
      if (!response.result.ok) {
        setProblem(response.result.message);
        return;
      }
      await refreshDefault();
    } catch {
      setProblem(t("settings.model.unavailable"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      className="capability-section"
      aria-labelledby="model-default-settings-title"
    >
      <div className="capability-section-heading">
        <h2 id="model-default-settings-title">
          {t("settings.tab.modelDefault")}
        </h2>
        {current && (
          <span className="settings-state">
            {current.label ?? current.status}
          </span>
        )}
      </div>
      <form className="capability-form" onSubmit={(event) => void save(event)}>
        <label>
          <span>{t("settings.model.label")}</span>
          <select
            value={selected}
            onChange={(event) => setSelected(event.target.value)}
            disabled={!canMutate || busy || models === null}
          >
            <option value="">{t("settings.model.hostDefault")}</option>
            {(models ?? []).map((model) => (
              <option key={model.id} value={model.id}>
                {model.label}
              </option>
            ))}
          </select>
        </label>
        <div className="capability-form-actions">
          <button
            type="submit"
            className="primary"
            disabled={!canMutate || busy || !selected}
          >
            {t("settings.model.save")}
          </button>
          <button
            type="button"
            disabled={!canMutate || busy || !current?.model_id}
            onClick={() => void clear()}
          >
            {t("settings.model.clear")}
          </button>
        </div>
      </form>
      {problem && <div className="capability-problem">{problem}</div>}
      {models === null && (
        <div className="capability-loading">{t("settings.loading")}</div>
      )}
      {models !== null && models.length === 0 && (
        <EmptySection message={t("settings.model.empty")} />
      )}
    </section>
  );
}
