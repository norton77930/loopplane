import { useRef, useState } from "react";
import { act, fireEvent, render, screen } from "@testing-library/react";

import { AppShell } from "../components/AppShell";

describe("AppShell responsive state", () => {
  beforeEach(() => {
    window.matchMedia = vi.fn().mockReturnValue({
      matches: true,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
    }) as unknown as typeof window.matchMedia;
  });

  it("exposes collapsed and mobile navigation state without owning application data", () => {
    const onDismissSidebar = vi.fn();
    const { container } = render(
      <AppShell
        sidebar={<div>Sessions</div>}
        header={<header>Header</header>}
        composer={<div>Composer</div>}
        sidebarCollapsed
        mobileSidebarOpen
        onDismissSidebar={onDismissSidebar}
      >
        <main>Messages</main>
      </AppShell>,
    );

    const shell = container.querySelector(".shell");
    expect(shell).toHaveAttribute("data-sidebar-collapsed", "true");
    expect(shell).toHaveAttribute("data-mobile-sidebar-open", "true");
    expect(screen.getByRole("dialog", { name: "Session navigation" }))
      .toHaveAttribute("aria-modal", "true");

    fireEvent.click(screen.getByRole("button", { name: "Close session navigation" }));
    expect(onDismissSidebar).toHaveBeenCalledOnce();
  });

  it("provides accessible dismissal controls for an overlay inspection panel", () => {
    const onDismissPanel = vi.fn();
    render(
      <AppShell
        sidebar={<div>Sessions</div>}
        header={<header>Header</header>}
        composer={<div>Composer</div>}
        panel={<aside>Inspection details</aside>}
        onDismissPanel={onDismissPanel}
      >
        <main>Messages</main>
      </AppShell>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Close inspection panel" }));
    expect(onDismissPanel).toHaveBeenCalledOnce();
  });

  it("closes an overlay panel on Escape and restores focus to its opener", () => {
    function Harness() {
      const [open, setOpen] = useState(false);
      return (
        <>
          <button type="button" onClick={() => setOpen(true)}>Open inspection</button>
          <AppShell
            sidebar={<div>Sessions</div>}
            header={<header>Header</header>}
            composer={<div>Composer</div>}
            panel={open ? <aside>Inspection details</aside> : undefined}
            onDismissPanel={() => setOpen(false)}
          >
            <main>Messages</main>
          </AppShell>
        </>
      );
    }

    render(<Harness />);
    const opener = screen.getByRole("button", { name: "Open inspection" });
    opener.focus();
    fireEvent.click(opener);

    const dialog = screen.getByRole("dialog", { name: "Inspection panel" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(document.activeElement).toBe(
      screen.getByRole("button", { name: "Close inspection panel" }),
    );

    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: "Inspection panel" })).toBeNull();
    expect(document.activeElement).toBe(opener);
  });

  it("keeps a stable focus return target across inspection mode changes", () => {
    let matches = false;
    const listeners = new Set<() => void>();
    window.matchMedia = vi.fn().mockReturnValue({
      get matches() {
        return matches;
      },
      addEventListener: (_event: string, listener: () => void) => listeners.add(listener),
      removeEventListener: (_event: string, listener: () => void) => listeners.delete(listener),
    }) as unknown as typeof window.matchMedia;

    function Harness() {
      const [open, setOpen] = useState(true);
      const openerRef = useRef<HTMLButtonElement>(null);
      return (
        <>
          <button ref={openerRef} type="button" onClick={() => setOpen(true)}>
            Open inspection
          </button>
          <AppShell
            sidebar={<div>Sessions</div>}
            header={<header>Header</header>}
            composer={<div>Composer</div>}
            panel={open ? <aside><button type="button">Panel action</button></aside> : undefined}
            onDismissPanel={() => setOpen(false)}
            panelReturnFocusRef={openerRef}
          >
            <main>Messages</main>
          </AppShell>
        </>
      );
    }

    render(<Harness />);
    const panelAction = screen.getByRole("button", { name: "Panel action" });
    panelAction.focus();

    act(() => {
      matches = true;
      listeners.forEach((listener) => listener());
    });
    expect(screen.getByRole("dialog", { name: "Inspection panel" })).toBeInTheDocument();
    expect(document.activeElement).toBe(
      screen.getByRole("button", { name: "Close inspection panel" }),
    );

    act(() => {
      matches = false;
      listeners.forEach((listener) => listener());
    });
    expect(screen.queryByRole("dialog", { name: "Inspection panel" })).toBeNull();
    expect(document.activeElement).not.toBe(
      screen.getByRole("button", { name: "Open inspection" }),
    );

    act(() => {
      matches = true;
      listeners.forEach((listener) => listener());
    });
    fireEvent.keyDown(screen.getByRole("dialog", { name: "Inspection panel" }), {
      key: "Escape",
    });
    expect(screen.queryByRole("dialog", { name: "Inspection panel" })).toBeNull();
    expect(document.activeElement).toBe(
      screen.getByRole("button", { name: "Open inspection" }),
    );
  });
});
