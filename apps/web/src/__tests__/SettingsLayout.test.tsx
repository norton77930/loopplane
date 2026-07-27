import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";

import { SettingsLayout } from "../components/settings/SettingsLayout";

function Harness() {
  const [activeId, setActiveId] = useState("memory");
  return (
    <SettingsLayout
      title="Settings"
      items={[
        { id: "memory", label: "Memory" },
        { id: "skills", label: "Skills" },
        { id: "mcp", label: "MCP" },
      ]}
      activeId={activeId}
      onSelect={setActiveId}
      backLabel="Back"
    >
      <div>{activeId}</div>
    </SettingsLayout>
  );
}

describe("SettingsLayout keyboard navigation", () => {
  it("uses roving tab focus with arrow, Home, and End keys", () => {
    render(<Harness />);
    const memory = screen.getByRole("tab", { name: "Memory" });
    const skills = screen.getByRole("tab", { name: "Skills" });
    const mcp = screen.getByRole("tab", { name: "MCP" });

    expect(memory).toHaveAttribute("tabindex", "0");
    expect(skills).toHaveAttribute("tabindex", "-1");

    memory.focus();
    fireEvent.keyDown(memory, { key: "ArrowDown" });
    expect(skills).toHaveAttribute("aria-selected", "true");
    expect(document.activeElement).toBe(skills);

    fireEvent.keyDown(skills, { key: "End" });
    expect(mcp).toHaveAttribute("aria-selected", "true");
    expect(document.activeElement).toBe(mcp);

    fireEvent.keyDown(mcp, { key: "Home" });
    expect(memory).toHaveAttribute("aria-selected", "true");
    expect(document.activeElement).toBe(memory);
  });
});
