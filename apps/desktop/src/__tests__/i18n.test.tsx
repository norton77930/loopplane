import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { SessionSidebar } from "../components/SessionSidebar";
import { DesktopI18nProvider } from "../i18n";

function sidebar() {
  return render(
    <DesktopI18nProvider>
      <SessionSidebar
        sessions={[{ session_id: "s1", title: "Fix the CI failure" }]}
        projects={[{ id: "p1", label: "Alpha", session_ids: [] }]}
        workspaces={[
          { id: "w1", label: "loopplane", availability: "relink_required", actions: [] },
        ]}
        selectedWorkspaceId="w1"
        onSelectSession={() => undefined}
        onNewSession={() => undefined}
        onToggleStar={() => undefined}
        onDeleteSession={() => undefined}
        onForkSession={() => undefined}
        onCreateProject={() => undefined}
        onRemoveProject={() => undefined}
        onBindWorkspace={() => undefined}
        onRelinkWorkspace={() => undefined}
        onSelectWorkspace={() => undefined}
        onOpenSettings={() => undefined}
      />
    </DesktopI18nProvider>,
  );
}

describe("Desktop chrome localization", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("starts in English", () => {
    sidebar();

    expect(screen.getByText("New session")).toBeInTheDocument();
    expect(screen.getByText("Folder moved")).toBeInTheDocument();
  });

  it("switches the whole sidebar when the language changes", () => {
    sidebar();

    fireEvent.change(screen.getByLabelText("Language"), {
      target: { value: "zh-TW" },
    });

    expect(screen.getByText("新工作階段")).toBeInTheDocument();
    expect(screen.getByText("資料夾已移動")).toBeInTheDocument();
    expect(screen.getByText("設定")).toBeInTheDocument();
    expect(screen.queryByText("New session")).not.toBeInTheDocument();
  });

  it("interpolates into a translated string", () => {
    sidebar();

    fireEvent.change(screen.getByLabelText("Language"), {
      target: { value: "zh-TW" },
    });

    // The switcher relabels itself along with everything else.
    expect(screen.getByLabelText("語言")).toBeInTheDocument();
    expect(screen.getByLabelText("移除專案 Alpha")).toBeInTheDocument();
  });

  it("never translates the fixed packaged-smoke locators", () => {
    // `Find-UniqueElement` matches these names literally, so a locale change
    // must not touch them.
    sidebar();
    fireEvent.change(screen.getByLabelText("Language"), {
      target: { value: "zh-TW" },
    });

    expect(
      screen.getByRole("button", { name: "LoopPlane smoke new session" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("list", { name: "LoopPlane smoke session list" }),
    ).toBeInTheDocument();
  });

  it("translates every string it owns", async () => {
    // A key present in English and missing in zh-TW renders as the key itself,
    // which is how "posture.plan" ends up in the middle of a Chinese sentence.
    const module = await import("../i18n");
    const source = (module as unknown as { __messages?: unknown }).__messages;
    expect(source).toBeDefined();
    const maps = source as Record<string, Record<string, string>>;
    const missing = Object.keys(maps.en!).filter((key) => !maps["zh-TW"]![key]);

    expect(missing, `untranslated: ${missing.join(", ")}`).toEqual([]);
  });

  it("remembers the choice under the key Web also uses", () => {
    sidebar();

    fireEvent.change(screen.getByLabelText("Language"), {
      target: { value: "zh-TW" },
    });

    expect(localStorage.getItem("loopplane-locale")).toBe("zh-TW");
  });
});
