import type { ReactNode } from "react";

import { useTranslation } from "../../i18n/i18n";
import { Modal } from "../Modal";

// Moved from apps/web in 083 Wave 3; apps/web re-exports it unchanged.
export interface CapabilityDetailField {
  label: string;
  value: ReactNode;
}

export function CapabilityDetail({
  title,
  fields,
  actions,
  onClose,
}: {
  title: string;
  fields: readonly CapabilityDetailField[];
  actions?: ReactNode;
  onClose: () => void;
}) {
  const { t } = useTranslation();

  return (
    <Modal onClose={onClose} label={`${title} ${t("settings.detail.title")}`}>
      <section className="capability-detail">
        <div className="capability-detail-heading">
          <h2>{title}</h2>
          <button type="button" onClick={onClose}>
            {t("settings.detail.close")}
          </button>
        </div>
        <dl className="capability-detail-fields">
          {fields.map((field) => {
            const unavailable =
              field.value === null ||
              field.value === undefined ||
              field.value === "";
            return (
              <div key={field.label}>
                <dt>{field.label}</dt>
                <dd>
                  {unavailable ? t("settings.detail.unavailable") : field.value}
                </dd>
              </div>
            );
          })}
        </dl>
        {actions && <div className="capability-detail-actions">{actions}</div>}
      </section>
    </Modal>
  );
}
