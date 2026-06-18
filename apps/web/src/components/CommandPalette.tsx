import { useEffect, useState } from "react";

// A composer command palette (029, FR-006/007): a leading `/` lists frontend-doable commands; a
// trailing `@<query>` autocompletes skill/tool mentions from the unit-027 inspection data.
// Backend-semantic commands are never passed in, so they are never offered.
export interface PaletteCommand {
  id: string;
  label: string;
}

interface Props {
  text: string;
  commands: PaletteCommand[];
  loadMentions: (query: string) => Promise<string[]>;
  onRunCommand: (id: string) => void;
  onInsertMention: (name: string) => void;
}

function parse(text: string): { mode: "slash" | "mention" | "none"; query: string } {
  if (text.startsWith("/") && !text.includes(" ")) {
    return { mode: "slash", query: text.slice(1) };
  }
  const mention = text.match(/(?:^|\s)@(\w*)$/);
  if (mention) return { mode: "mention", query: mention[1] };
  return { mode: "none", query: "" };
}

export function CommandPalette({
  text,
  commands,
  loadMentions,
  onRunCommand,
  onInsertMention,
}: Props) {
  const { mode, query } = parse(text);
  const [mentions, setMentions] = useState<string[]>([]);

  useEffect(() => {
    if (mode !== "mention") return;
    let live = true;
    void loadMentions(query)
      .then((result) => live && setMentions(result))
      .catch(() => live && setMentions([]));
    return () => {
      live = false;
    };
  }, [mode, query, loadMentions]);

  if (mode === "none") return null;

  if (mode === "slash") {
    const lower = query.toLowerCase();
    const matches = commands.filter(
      (command) => command.id.includes(lower) || command.label.toLowerCase().includes(lower),
    );
    if (matches.length === 0) return null;
    return (
      <ul className="palette" role="listbox" aria-label="commands">
        {matches.map((command) => (
          <li key={command.id}>
            <button type="button" onClick={() => onRunCommand(command.id)}>
              {command.label}
            </button>
          </li>
        ))}
      </ul>
    );
  }

  if (mentions.length === 0) return null;
  return (
    <ul className="palette" role="listbox" aria-label="mentions">
      {mentions.map((name) => (
        <li key={name}>
          <button type="button" onClick={() => onInsertMention(name)}>
            @{name}
          </button>
        </li>
      ))}
    </ul>
  );
}
