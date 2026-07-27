import { useRef, type KeyboardEvent, type ReactNode } from "react";

import { useTranslation } from "../../i18n/i18n";
import { ArrowLeftIcon } from "../icons/Icons";

export interface SettingsNavItem {
  id: string;
  label: string;
}

interface Props {
  title: string;
  status?: ReactNode;
  items: SettingsNavItem[];
  activeId: string;
  onSelect: (id: string) => void;
  onBack?: () => void;
  backLabel: string;
  children: ReactNode;
}

export function SettingsLayout({
  title,
  status,
  items,
  activeId,
  onSelect,
  onBack,
  backLabel,
  children,
}: Props) {
  const { t } = useTranslation();
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const active = items.find((item) => item.id === activeId) ?? items[0];

  function selectAndFocus(index: number) {
    const item = items[index];
    if (!item) return;
    onSelect(item.id);
    tabRefs.current[index]?.focus();
  }

  function onTabKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    let nextIndex: number | undefined;
    if (event.key === "ArrowDown") nextIndex = (index + 1) % items.length;
    if (event.key === "ArrowUp") nextIndex = (index - 1 + items.length) % items.length;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = items.length - 1;
    if (nextIndex === undefined) return;
    event.preventDefault();
    selectAndFocus(nextIndex);
  }

  return (
    <main className="capability-settings">
      <header className="capability-settings-header">
        {onBack ? (
          <button type="button" className="settings-back" onClick={onBack}>
            <ArrowLeftIcon />
            <span>{backLabel}</span>
          </button>
        ) : null}
        <div className="settings-title-group">
          <h1>{title}</h1>
          {status}
        </div>
      </header>
      <div className="capability-settings-workspace">
        <div
          className="capability-settings-tabs"
          role="tablist"
          aria-label={t("settings.categories")}
          aria-orientation="vertical"
        >
          {items.map((item, index) => (
            <button
              key={item.id}
              ref={(node) => {
                tabRefs.current[index] = node;
              }}
              id={`settings-tab-${item.id}`}
              type="button"
              role="tab"
              aria-selected={activeId === item.id}
              aria-controls={`settings-panel-${item.id}`}
              tabIndex={activeId === item.id ? 0 : -1}
              className={activeId === item.id ? "active" : ""}
              onClick={() => onSelect(item.id)}
              onKeyDown={(event) => onTabKeyDown(event, index)}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div
          id={`settings-panel-${active.id}`}
          className="capability-settings-body"
          role="tabpanel"
          aria-labelledby={`settings-tab-${active.id}`}
        >
          {children}
        </div>
      </div>
    </main>
  );
}
