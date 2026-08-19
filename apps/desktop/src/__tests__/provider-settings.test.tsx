import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  ProviderSettings,
  type ProviderSettingsPort,
} from "../components/ProviderSettings";
import type { ProviderSaveResult, ProviderView } from "../global";

const FAKE_KEY = "sk-ant-api03-abcdefghijklmnop4f2a";

function port(
  overrides: Partial<ProviderSettingsPort> = {},
): ProviderSettingsPort & { saves: unknown[]; restarts: number } {
  const saves: unknown[] = [];
  const base = {
    saves,
    restarts: 0,
    get: async (): Promise<ProviderView | null> => null,
    save: async (input: unknown): Promise<ProviderSaveResult> => {
      saves.push(input);
      return { ok: true };
    },
    clear: async () => ({ ok: true }) as const,
    restart: async function (this: { restarts: number }) {
      this.restarts += 1;
      return { ok: true } as const;
    },
    catalog: async () => [],
  };
  return Object.assign(base, overrides);
}

describe("ProviderSettings", () => {
  it("says plainly that no provider is set up yet", async () => {
    render(<ProviderSettings port={port()} />);

    expect(await screen.findByText(/no provider is set up/i)).toBeInTheDocument();
  });

  it("shows the stored provider without showing the key", async () => {
    render(
      <ProviderSettings
        port={port({
          get: async () => ({
            provider: "anthropic",
            modelId: "claude-x",
            hasKey: true,
            keyHint: "…4f2a",
          }),
        })}
      />,
    );

    expect(await screen.findByText(/claude-x/)).toBeInTheDocument();
    expect(screen.getByText(/…4f2a/)).toBeInTheDocument();
    expect(document.body.textContent ?? "").not.toContain(FAKE_KEY);
  });

  it("keeps the key field masked", async () => {
    render(<ProviderSettings port={port()} />);

    const key = await screen.findByLabelText(/api key/i);
    expect(key).toHaveAttribute("type", "password");
  });

  it("saves the trimmed provider, model id and key", async () => {
    const p = port();
    render(<ProviderSettings port={p} />);

    fireEvent.change(await screen.findByLabelText(/model/i), {
      target: { value: "  claude-x  " },
    });
    fireEvent.change(screen.getByLabelText(/api key/i), {
      target: { value: ` ${FAKE_KEY} ` },
    });
    fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() =>
      expect(p.saves).toEqual([
        { provider: "anthropic", modelId: "claude-x", apiKey: FAKE_KEY },
      ]),
    );
  });

  it("stops asking for a key once a keyless provider is chosen", async () => {
    const p = port();
    render(<ProviderSettings port={p} />);

    fireEvent.change(await screen.findByLabelText(/provider/i), {
      target: { value: "ollama" },
    });

    expect(screen.queryByLabelText(/api key/i)).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/model/i), {
      target: { value: "llama3" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() =>
      expect(p.saves).toEqual([
        { provider: "ollama", modelId: "llama3", apiKey: null },
      ]),
    );
  });

  it.each([
    ["encryption_unavailable", /cannot store a key securely/i],
    ["invalid_model_id", /model id/i],
    ["missing_key", /needs an api key/i],
    ["write_failed", /could not be saved/i],
  ])("explains a %s failure in plain words", async (reason, pattern) => {
    render(
      <ProviderSettings
        port={port({
          save: async () => ({
            ok: false,
            reason,
          }) as ProviderSaveResult,
        })}
      />,
    );

    fireEvent.change(await screen.findByLabelText(/model/i), {
      target: { value: "claude-x" },
    });
    fireEvent.change(screen.getByLabelText(/api key/i), {
      target: { value: FAKE_KEY },
    });
    fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(pattern);
    expect(screen.getByRole("alert").textContent ?? "").not.toContain(reason);
  });

  it("refuses a blank model id locally instead of letting the boundary reject", async () => {
    // The IPC layer answers a blank field by rejecting, not by returning a
    // reason, so a component that only handled results left the user with a
    // screen that silently did nothing.
    const p = port({
      save: async () => {
        throw new Error("invalid params");
      },
    });
    render(<ProviderSettings port={p} />);

    fireEvent.change(await screen.findByLabelText(/api key/i), {
      target: { value: FAKE_KEY },
    });
    fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/model id/i);
    expect(p.saves).toEqual([]);
  });

  it("asks for a key when none is stored yet", async () => {
    const p = port();
    render(<ProviderSettings port={p} />);

    fireEvent.change(await screen.findByLabelText(/model/i), {
      target: { value: "claude-x" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/needs an api key/i);
    expect(p.saves).toEqual([]);
  });

  it("lets a stored key stand when only the model changes", async () => {
    const p = port({
      get: async () => ({
        provider: "anthropic",
        modelId: "claude-old",
        hasKey: true,
        keyHint: "…4f2a",
      }),
    });
    render(<ProviderSettings port={p} />);

    fireEvent.change(await screen.findByLabelText(/model/i), {
      target: { value: "claude-new" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() =>
      expect(p.saves).toEqual([
        { provider: "anthropic", modelId: "claude-new", apiKey: null },
      ]),
    );
  });

  it("still demands a key when the provider changes", async () => {
    const p = port({
      get: async () => ({
        provider: "anthropic",
        modelId: "claude-x",
        hasKey: true,
        keyHint: "…4f2a",
      }),
    });
    render(<ProviderSettings port={p} />);

    fireEvent.change(await screen.findByLabelText(/provider/i), {
      target: { value: "openai" },
    });
    fireEvent.change(screen.getByLabelText(/model/i), {
      target: { value: "gpt-x" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/needs an api key/i);
    expect(p.saves).toEqual([]);
  });

  it("surfaces a rejected save instead of swallowing it", async () => {
    const p = port({
      save: async () => {
        throw new Error("stale IPC registration");
      },
    });
    render(<ProviderSettings port={p} />);

    fireEvent.change(await screen.findByLabelText(/model/i), {
      target: { value: "claude-x" },
    });
    fireEvent.change(screen.getByLabelText(/api key/i), {
      target: { value: FAKE_KEY },
    });
    fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/could not be saved/i);
    expect(alert.textContent ?? "").not.toContain("stale IPC registration");
  });

  it("offers a restart only after a successful save", async () => {
    const p = port();
    render(<ProviderSettings port={p} />);

    expect(
      screen.queryByRole("button", { name: /restart loopplane/i }),
    ).not.toBeInTheDocument();

    fireEvent.change(await screen.findByLabelText(/model/i), {
      target: { value: "claude-x" },
    });
    fireEvent.change(screen.getByLabelText(/api key/i), {
      target: { value: FAKE_KEY },
    });
    fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

    const restart = await screen.findByRole("button", { name: /restart loopplane/i });
    fireEvent.click(restart);

    await waitFor(() => expect(p.restarts).toBe(1));
  });

  it("tells the user where the key is kept and that backups exclude it", async () => {
    render(<ProviderSettings port={port()} />);

    const note = await screen.findByTestId("provider-storage-note");
    expect(note.textContent ?? "").toMatch(/this computer/i);
    expect(note.textContent ?? "").toMatch(/backup/i);
  });

  it("removes a stored provider on request", async () => {
    const clear = vi.fn(async () => ({ ok: true }) as const);
    render(
      <ProviderSettings
        port={port({
          clear,
          get: async () => ({
            provider: "openai",
            modelId: "gpt-x",
            hasKey: true,
            keyHint: "…9999",
          }),
        })}
      />,
    );

    fireEvent.click(await screen.findByRole("button", { name: /remove/i }));

    await waitFor(() => expect(clear).toHaveBeenCalled());
  });
});

describe("ProviderSettings one-step model switch (083 W2-A)", () => {
  const CATALOG = [
    {
      provider: "anthropic",
      models: [
        { id: "claude-opus-5", current: false },
        { id: "claude-sonnet-5", current: true },
      ],
    },
    { provider: "openai", models: [{ id: "gpt-4o", current: false }] },
  ];

  it("offers the selected provider's catalog as datalist options", async () => {
    render(<ProviderSettings port={port({ catalog: async () => CATALOG })} />);

    const model = await screen.findByLabelText(/model/i);
    await waitFor(() =>
      expect(document.querySelectorAll("datalist option").length).toBeGreaterThan(0),
    );
    const values = [...document.querySelectorAll("datalist option")].map(
      (o) => (o as HTMLOptionElement).value,
    );
    expect(values).toContain("claude-opus-5");
    // gpt-4o belongs to openai, which is not the selected provider.
    expect(values).not.toContain("gpt-4o");
    expect(model.getAttribute("list")).toBe(
      document.querySelector("datalist")?.id,
    );
  });

  it("renders no options when the catalog has nothing for the provider", async () => {
    render(<ProviderSettings port={port({ catalog: async () => [] })} />);

    await screen.findByLabelText(/model/i);
    expect(document.querySelectorAll("datalist option")).toHaveLength(0);
  });

  it("saves then restarts in one step, reusing the stored key", async () => {
    const p = port({
      get: async () => ({
        provider: "anthropic",
        modelId: "claude-x",
        hasKey: true,
        keyHint: "…4f2a",
      }),
      catalog: async () => CATALOG,
    });
    render(<ProviderSettings port={p} />);

    const model = await screen.findByLabelText(/model/i);
    fireEvent.change(model, { target: { value: "claude-opus-5" } });
    fireEvent.click(screen.getByRole("button", { name: /save & restart/i }));

    await waitFor(() => expect(p.restarts).toBe(1));
    // The empty key box reuses the stored key: apiKey travels as null.
    expect(p.saves).toEqual([
      { provider: "anthropic", modelId: "claude-opus-5", apiKey: null },
    ]);
  });

  it("does not restart when the save is refused locally", async () => {
    const p = port({ catalog: async () => CATALOG });
    render(<ProviderSettings port={p} />);

    // No stored key and an empty key box: the local missing_key check refuses.
    const model = await screen.findByLabelText(/model/i);
    fireEvent.change(model, { target: { value: "claude-opus-5" } });
    fireEvent.click(screen.getByRole("button", { name: /save & restart/i }));

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(p.restarts).toBe(0);
    expect(p.saves).toEqual([]);
  });

  it("disables the one-step action while a run is in flight", async () => {
    render(
      <ProviderSettings port={port({ catalog: async () => CATALOG })} runActive />,
    );

    const button = await screen.findByRole("button", { name: /save & restart/i });
    expect(button).toBeDisabled();
    expect(screen.getByText(/current run/i)).toBeInTheDocument();
  });
});
