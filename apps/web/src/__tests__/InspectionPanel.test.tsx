import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import type { ApiClient } from "../api/client";
import { InspectionPanel } from "../components/InspectionPanel";
import { I18nProvider } from "../i18n/i18n";

function stubClient(overrides: Record<string, unknown> = {}): ApiClient {
  return {
    inspectSkills: async () => ({
      skills: [
        { name: "writer", description: "writes things", autonomous: true, approval_required: false, source: "skills" },
      ],
      problems: [],
    }),
    inspectTools: async () => [
      { name: "echo", description: "echoes", read_only: true, source: "internal" },
    ],
    inspectMcp: async () => [],
    inspectMemory: async () => [
      { type: "user", name: "pref", description: "a preference", snippet: "likes tabs" },
    ],
    ...overrides,
  } as unknown as ApiClient;
}

describe("InspectionPanel", () => {
  it("distinguishes loading from empty data", () => {
    const client = stubClient({
      inspectSkills: () => new Promise(() => undefined),
    });
    render(<InspectionPanel client={client} />);

    expect(screen.getByRole("status")).toHaveTextContent("Loading skills");
    expect(screen.queryByText(/No skills/)).toBeNull();
  });

  it("distinguishes a request failure from empty data", async () => {
    render(
      <InspectionPanel
        client={stubClient({
          inspectSkills: async () => {
            throw new Error("offline");
          },
        })}
      />,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Unable to load skills",
    );
    expect(screen.queryByText(/No skills/)).toBeNull();
  });

  it("shows skills on open and switches to tools", async () => {
    render(<InspectionPanel client={stubClient()} />);
    expect(await screen.findByText("writer")).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Capabilities" })).toBeNull();
    fireEvent.click(screen.getByRole("tab", { name: "Tools" }));
    expect(await screen.findByText("echo")).toBeInTheDocument();
  });

  it("uses roving tab focus for inspection categories", async () => {
    render(<InspectionPanel client={stubClient()} />);
    const skills = screen.getByRole("tab", { name: "Skills" });
    const tools = screen.getByRole("tab", { name: "Tools" });

    expect(skills).toHaveAttribute("tabindex", "0");
    expect(tools).toHaveAttribute("tabindex", "-1");
    skills.focus();
    fireEvent.keyDown(skills, { key: "ArrowRight" });

    expect(tools).toHaveAttribute("aria-selected", "true");
    expect(document.activeElement).toBe(tools);
    expect(await screen.findByText("echo")).toBeInTheDocument();
  });

  it("shows a clear empty state for MCP with no servers", async () => {
    render(<InspectionPanel client={stubClient()} />);
    fireEvent.click(screen.getByRole("tab", { name: "MCP" }));
    expect(await screen.findByText(/No MCP servers/)).toBeInTheDocument();
  });

  it("searches memory by re-fetching with the query", async () => {
    const inspectMemory = vi.fn().mockResolvedValue([
      { type: "user", name: "pref", description: "d", snippet: "s" },
    ]);
    render(<InspectionPanel client={stubClient({ inspectMemory })} />);
    fireEvent.click(screen.getByRole("tab", { name: "Memory" }));
    await screen.findByText("pref");
    fireEvent.change(screen.getByLabelText("search memory"), { target: { value: "tabs" } });
    await waitFor(() => expect(inspectMemory).toHaveBeenCalledWith("tabs"));
  });

  it("localizes inspection chrome in Traditional Chinese", async () => {
    localStorage.setItem("loopplane-locale", "zh-TW");
    render(
      <I18nProvider>
        <InspectionPanel
          client={stubClient({ inspectSkills: () => new Promise(() => undefined) })}
        />
      </I18nProvider>,
    );

    expect(screen.getByRole("complementary", { name: "\u6aa2\u8996\u9762\u677f" }))
      .toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "\u6280\u80fd" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "\u5de5\u5177" })).toBeInTheDocument();
    localStorage.removeItem("loopplane-locale");
  });
});
