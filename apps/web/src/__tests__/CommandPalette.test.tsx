import { fireEvent, render, screen } from "@testing-library/react";

import { CommandPalette } from "../components/CommandPalette";

const COMMANDS = [{ id: "toggle-inspect", label: "Toggle inspection panel" }];

describe("CommandPalette", () => {
  it("lists frontend commands on slash and runs one", () => {
    const onRunCommand = vi.fn();
    render(
      <CommandPalette
        text="/"
        commands={COMMANDS}
        loadMentions={async () => []}
        onRunCommand={onRunCommand}
        onInsertMention={() => undefined}
      />,
    );
    fireEvent.click(screen.getByText("Toggle inspection panel"));
    expect(onRunCommand).toHaveBeenCalledWith("toggle-inspect");
  });

  it("autocompletes @-mentions from the inspection data", async () => {
    const onInsertMention = vi.fn();
    const loadMentions = vi.fn().mockResolvedValue(["writer", "search"]);
    render(
      <CommandPalette
        text="@wr"
        commands={[]}
        loadMentions={loadMentions}
        onRunCommand={() => undefined}
        onInsertMention={onInsertMention}
      />,
    );
    expect(await screen.findByText("@writer")).toBeInTheDocument();
    fireEvent.click(screen.getByText("@writer"));
    expect(onInsertMention).toHaveBeenCalledWith("writer");
    expect(loadMentions).toHaveBeenCalledWith("wr");
  });

  it("never offers a backend-semantic command", () => {
    render(
      <CommandPalette
        text="/"
        commands={COMMANDS}
        loadMentions={async () => []}
        onRunCommand={() => undefined}
        onInsertMention={() => undefined}
      />,
    );
    expect(screen.queryByText(/compact|schedule|plan mode/i)).toBeNull();
  });
});
