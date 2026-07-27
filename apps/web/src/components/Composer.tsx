import { useEffect, useRef, useState, type ReactNode } from "react";

import { useTranslation } from "../i18n/i18n";
import { CommandPalette, type PaletteCommand } from "./CommandPalette";
import { SendIcon } from "./icons/Icons";

// A sticky composer (FR-012): a textarea that grows and disables sending while a run is in flight.
// `extras` hosts the composer controls (model selector + attachments, 028). A command palette (029)
// opens on a leading `/` or a trailing `@<query>`.
interface Props {
  disabled: boolean;
  sendDisabled?: boolean;
  onSend: (text: string) => void;
  value?: string;
  onValueChange?: (value: string) => void;
  focusToken?: number;
  extras?: ReactNode;
  commands?: PaletteCommand[];
  loadMentions?: (query: string) => Promise<string[]>;
  onCommand?: (id: string) => void;
}

const MAX_HEIGHT = 200;

export function Composer({
  disabled,
  sendDisabled = false,
  onSend,
  value: controlledValue,
  onValueChange,
  focusToken,
  extras,
  commands = [],
  loadMentions,
  onCommand,
}: Props) {
  const { t } = useTranslation();
  const [internalValue, setInternalValue] = useState("");
  const value = controlledValue ?? internalValue;
  const ref = useRef<HTMLTextAreaElement>(null);

  function setValue(next: string | ((current: string) => string)) {
    const resolved = typeof next === "function" ? next(value) : next;
    if (controlledValue === undefined) setInternalValue(resolved);
    onValueChange?.(resolved);
  }

  useEffect(() => {
    if (focusToken !== undefined) ref.current?.focus();
  }, [focusToken]);

  function grow() {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT)}px`;
  }

  function submit() {
    const text = value.trim();
    if (!text || disabled || sendDisabled) return;
    onSend(text);
    setValue("");
    if (ref.current) ref.current.style.height = "auto";
  }

  function insertMention(name: string) {
    setValue((current) => current.replace(/@(\w*)$/, `@${name} `));
    ref.current?.focus();
  }

  function runCommand(id: string) {
    setValue("");
    onCommand?.(id);
  }

  return (
    <div className="composer-area">
      <div className="composer-surface">
        <CommandPalette
          text={value}
          commands={commands}
          loadMentions={loadMentions ?? (async () => [])}
          onRunCommand={runCommand}
          onInsertMention={insertMention}
        />
        <form
          className="composer"
          onSubmit={(event) => {
            event.preventDefault();
            submit();
          }}
        >
          <textarea
            ref={ref}
            aria-label="prompt"
            rows={1}
            value={value}
            disabled={disabled}
            placeholder={t("composer.placeholder")}
            onChange={(event) => {
              setValue(event.target.value);
              grow();
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                submit();
              }
            }}
          />
          <button
            type="submit"
            className="primary composer-send"
            disabled={disabled || sendDisabled || !value.trim()}
          >
            <SendIcon />
            <span className="button-label">{t("composer.send")}</span>
          </button>
        </form>
        {extras ? <div className="composer-extras">{extras}</div> : null}
      </div>
    </div>
  );
}
