import { render, screen } from "@testing-library/react";

import { AppShell } from "../components/AppShell";

describe("AppShell characterization", () => {
  it("keeps the presentation slots in the application shell", () => {
    render(
      <AppShell
        sidebar={<div>Sessions</div>}
        header={<header>Conversation header</header>}
        banner={<div>Connection problem</div>}
        composer={<div>Prompt composer</div>}
        panel={<aside>Inspection</aside>}
      >
        <main>Messages</main>
      </AppShell>,
    );

    expect(screen.getByText("Sessions")).toBeInTheDocument();
    expect(screen.getByText("Conversation header")).toBeInTheDocument();
    expect(screen.getByText("Connection problem")).toBeInTheDocument();
    expect(screen.getByText("Messages")).toBeInTheDocument();
    expect(screen.getByText("Prompt composer")).toBeInTheDocument();
    expect(screen.getByText("Inspection")).toBeInTheDocument();
  });
});
