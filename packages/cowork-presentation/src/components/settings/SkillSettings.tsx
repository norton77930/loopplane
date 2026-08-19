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

export interface SkillRecord {
  id: string;
  name: string;
  description?: string | null;
  scope?: string | null;
  actions: readonly string[];
}

export interface SkillDetail extends SkillRecord {
  instructions: string;
  source?: string | null;
  status?: string | null;
}

export interface SkillDefinition {
  name: string;
  description: string;
  instructions: string;
}

export interface SkillSettingsService {
  list(): Promise<readonly SkillRecord[]>;
  get(id: string): Promise<SkillDetail>;
  write(definition: SkillDefinition): Promise<CapabilityActionResult>;
  import(definition: SkillDefinition): Promise<CapabilityActionResult>;
  remove(id: string): Promise<CapabilityActionResult>;
}

export function SkillSettings({
  service,
  canMutate,
}: {
  service: SkillSettingsService;
  canMutate: boolean;
}) {
  const { t } = useTranslation();
  const [skills, setSkills] = useState<readonly SkillRecord[] | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");
  const [instructions, setInstructions] = useState("");
  const [detail, setDetail] = useState<{
    title: string;
    fields: CapabilityDetailField[];
  } | null>(null);

  async function refresh() {
    try {
      setSkills(await service.list());
      setProblem(null);
    } catch {
      setSkills([]);
      setProblem(t("settings.skills.unavailable"));
    }
  }

  useEffect(() => {
    void refresh();
  }, [service]);

  function definition(): SkillDefinition {
    return { name, description: "", instructions };
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    try {
      const result = await service.write(definition());
      if (!result.ok) {
        setProblem(result.message);
        return;
      }
      await refresh();
    } catch {
      setProblem(t("settings.skills.unavailable"));
    } finally {
      setBusy(false);
    }
  }

  async function importSkill() {
    setBusy(true);
    try {
      const result = await service.import(definition());
      if (!result.ok) {
        setProblem(result.message);
        return;
      }
      await refresh();
    } catch {
      setProblem(t("settings.skills.unavailable"));
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    if (!window.confirm(t("settings.skills.deleteConfirm"))) return;
    setBusy(true);
    try {
      const result = await service.remove(id);
      if (!result.ok) {
        setProblem(result.message);
        return;
      }
      await refresh();
    } catch {
      setProblem(t("settings.skills.unavailable"));
    } finally {
      setBusy(false);
    }
  }

  async function open(skill: SkillRecord) {
    try {
      const loaded = await service.get(skill.id);
      if (skill.scope === "shared_read_only") {
        setDetail({
          title: loaded.name,
          fields: [
            {
              label: t("settings.detail.description"),
              value: loaded.description,
            },
            { label: t("settings.detail.source"), value: loaded.source },
            { label: t("settings.detail.status"), value: loaded.status },
          ],
        });
        return;
      }
      setName(loaded.name);
      setInstructions(loaded.instructions);
    } catch {
      setProblem(t("settings.skills.detailsUnavailable"));
    }
  }

  return (
    <section className="capability-section" aria-labelledby="skill-settings-title">
      <div className="capability-section-heading">
        <h2 id="skill-settings-title">{t("settings.tab.skills")}</h2>
      </div>
      <form className="capability-form" onSubmit={(event) => void save(event)}>
        <label>
          <span>{t("settings.skills.name")}</span>
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            disabled={!canMutate || busy}
            required
          />
        </label>
        <label>
          <span>{t("settings.skills.instructions")}</span>
          <textarea
            value={instructions}
            onChange={(event) => setInstructions(event.target.value)}
            disabled={!canMutate || busy}
            required
          />
        </label>
        <div className="capability-form-actions">
          <button
            type="submit"
            className="primary"
            disabled={!canMutate || busy}
          >
            {t("settings.skills.save")}
          </button>
          <button
            type="button"
            disabled={!canMutate || busy}
            onClick={() => void importSkill()}
          >
            {t("settings.skills.import")}
          </button>
        </div>
      </form>
      {problem && <div className="capability-problem">{problem}</div>}
      {skills === null ? (
        <div className="capability-loading">{t("settings.loading")}</div>
      ) : skills.length === 0 ? (
        <EmptySection message={t("settings.skills.empty")} />
      ) : (
        <ul className="capability-list">
          {skills.map((skill) => (
            <li
              key={skill.id}
              className="capability-item"
              data-testid={`skill-${skill.id}`}
            >
              <div className="capability-item-copy">
                <strong>{skill.name}</strong>
                <span>{skill.description}</span>
              </div>
              {skill.scope === "shared_read_only" && (
                <span className="settings-state">{t("settings.readOnly")}</span>
              )}
              <div className="capability-actions">
                {skill.actions.includes("open") && (
                  <button type="button" onClick={() => void open(skill)}>
                    {t("settings.action.open")}
                  </button>
                )}
                {skill.actions.includes("delete") && (
                  <button
                    type="button"
                    className="danger"
                    disabled={busy}
                    onClick={() => void remove(skill.id)}
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
