import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import { useTranslation } from "../../i18n/i18n";
import { EmptySection } from "./EmptySection";
import type { CapabilityActionResult } from "./McpSettings";

// Moved from apps/web in 083 Wave 3 behind a narrow service port (FR-020);
// apps/web adapts its HTTP client to this interface. Behavior is unchanged.

export interface ScheduleRecord {
  id: string;
  name: string;
  trigger: string;
  status?: string | null;
  scope?: string | null;
  actions: readonly string[];
}

export interface ScheduleDetail extends ScheduleRecord {
  instruction: string;
  enabled: boolean;
}

export interface ScheduleSettingsService {
  list(): Promise<readonly ScheduleRecord[]>;
  get(id: string): Promise<ScheduleDetail>;
  upsert(input: {
    name: string;
    description: string;
    trigger: string;
    instruction: string;
    enabled: boolean;
  }): Promise<CapabilityActionResult>;
  runNow(id: string): Promise<CapabilityActionResult>;
  enable(id: string): Promise<CapabilityActionResult>;
  disable(id: string): Promise<CapabilityActionResult>;
  remove(id: string): Promise<CapabilityActionResult>;
}

export function ScheduleSettings({
  service,
  canMutate,
}: {
  service: ScheduleSettingsService;
  canMutate: boolean;
}) {
  const { t } = useTranslation();
  const [schedules, setSchedules] = useState<readonly ScheduleRecord[] | null>(
    null,
  );
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");
  const [trigger, setTrigger] = useState("");
  const [instruction, setInstruction] = useState("");
  const [enabled, setEnabled] = useState(true);

  async function refresh() {
    try {
      setSchedules(await service.list());
      setProblem(null);
    } catch {
      setSchedules([]);
      setProblem(t("settings.schedules.unavailable"));
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
        trigger,
        instruction,
        enabled,
      });
      if (!result.ok) {
        setProblem(result.message);
        return;
      }
      await refresh();
    } catch {
      setProblem(t("settings.schedules.unavailable"));
    } finally {
      setBusy(false);
    }
  }

  async function open(id: string) {
    try {
      const schedule = await service.get(id);
      setName(schedule.name);
      setTrigger(schedule.trigger);
      setInstruction(schedule.instruction);
      setEnabled(schedule.enabled);
    } catch {
      setProblem(t("settings.schedules.detailsUnavailable"));
    }
  }

  async function runNow(id: string) {
    setBusy(true);
    try {
      const result = await service.runNow(id);
      if (!result.ok) {
        setProblem(result.message);
        return;
      }
      await refresh();
    } catch {
      setProblem(t("settings.schedules.runUnavailable"));
    } finally {
      setBusy(false);
    }
  }

  async function enable(id: string) {
    setBusy(true);
    try {
      const result = await service.enable(id);
      if (!result.ok) {
        setProblem(result.message);
        return;
      }
      await refresh();
    } catch {
      setProblem(t("settings.schedules.unavailable"));
    } finally {
      setBusy(false);
    }
  }

  async function disable(id: string) {
    setBusy(true);
    try {
      const result = await service.disable(id);
      if (!result.ok) {
        setProblem(result.message);
        return;
      }
      await refresh();
    } catch {
      setProblem(t("settings.schedules.unavailable"));
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    if (!window.confirm(t("settings.schedules.deleteConfirm"))) return;
    setBusy(true);
    try {
      const result = await service.remove(id);
      if (!result.ok) {
        setProblem(result.message);
        return;
      }
      await refresh();
    } catch {
      setProblem(t("settings.schedules.unavailable"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      className="capability-section"
      aria-labelledby="schedule-settings-title"
    >
      <div className="capability-section-heading">
        <h2 id="schedule-settings-title">{t("settings.tab.schedules")}</h2>
      </div>
      <form className="capability-form" onSubmit={(event) => void save(event)}>
        <label>
          <span>{t("settings.schedules.name")}</span>
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            disabled={!canMutate || busy}
            required
          />
        </label>
        <label>
          <span>{t("settings.schedules.trigger")}</span>
          <input
            value={trigger}
            onChange={(event) => setTrigger(event.target.value)}
            disabled={!canMutate || busy}
            required
          />
        </label>
        <label>
          <span>{t("settings.schedules.instruction")}</span>
          <textarea
            value={instruction}
            onChange={(event) => setInstruction(event.target.value)}
            disabled={!canMutate || busy}
            required
          />
        </label>
        <label className="capability-checkbox">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(event) => setEnabled(event.target.checked)}
            disabled={!canMutate || busy}
          />
          <span>{t("settings.schedules.enabled")}</span>
        </label>
        <button
          type="submit"
          className="primary"
          disabled={!canMutate || busy}
        >
          {t("settings.schedules.save")}
        </button>
      </form>
      {problem && <div className="capability-problem">{problem}</div>}
      {schedules === null ? (
        <div className="capability-loading">{t("settings.loading")}</div>
      ) : schedules.length === 0 ? (
        <EmptySection message={t("settings.schedules.empty")} />
      ) : (
        <ul className="capability-list">
          {schedules.map((schedule) => (
            <li
              key={schedule.id}
              className="capability-item"
              data-testid={"schedule-" + schedule.id}
            >
              <div className="capability-item-copy">
                <strong>{schedule.name}</strong>
                <span>
                  {schedule.trigger} / {schedule.status}
                </span>
              </div>
              {schedule.scope === "shared_read_only" ? (
                <span className="settings-state">{t("settings.readOnly")}</span>
              ) : (
                <div className="capability-actions">
                  {schedule.actions.includes("open") && (
                    <button
                      type="button"
                      onClick={() => void open(schedule.id)}
                    >
                      {t("settings.action.open")}
                    </button>
                  )}
                  {schedule.actions.includes("run_now") && (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void runNow(schedule.id)}
                    >
                      {t("settings.action.runNow")}
                    </button>
                  )}
                  {schedule.actions.includes("enable") && (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void enable(schedule.id)}
                    >
                      {t("settings.action.enable")}
                    </button>
                  )}
                  {schedule.actions.includes("disable") && (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void disable(schedule.id)}
                    >
                      {t("settings.action.disable")}
                    </button>
                  )}
                  {schedule.actions.includes("delete") && (
                    <button
                      type="button"
                      className="danger"
                      disabled={busy}
                      onClick={() => void remove(schedule.id)}
                    >
                      {t("settings.action.delete")}
                    </button>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
