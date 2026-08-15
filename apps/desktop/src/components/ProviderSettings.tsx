/**
 * Provider settings (Unit A): the one screen that turns a fresh install into a
 * working app.
 *
 * Before this existed the only way to reach a real model was to export
 * `LOOPPLANE_MODEL=<python_module>:<attr>` before launching Electron, so anyone
 * who did not already know the runtime got "no provider is configured" forever.
 *
 * The key is write-only from here: it is sent once on save and never read back.
 * `port.get()` answers with a hint of the last four characters at most.
 */

import { useCallback, useEffect, useState } from "react";

import type { ProviderSaveResult, ProviderView } from "../global";

export type ProviderSettingsPort = {
  get(): Promise<ProviderView | null>;
  save(input: {
    provider: string;
    modelId: string;
    apiKey: string | null;
  }): Promise<ProviderSaveResult>;
  clear(): Promise<unknown>;
  restart(): Promise<unknown>;
};

type ProviderOption = {
  id: string;
  label: string;
  /** A real, current model id, so the field is not a guessing game. */
  example: string;
  keyless?: boolean;
};

const PROVIDERS: readonly ProviderOption[] = [
  { id: "anthropic", label: "Anthropic (Claude)", example: "claude-sonnet-5" },
  { id: "openai", label: "OpenAI", example: "gpt-4o" },
  { id: "gemini", label: "Google Gemini", example: "gemini-2.5-pro" },
  { id: "openrouter", label: "OpenRouter", example: "anthropic/claude-sonnet-5" },
  {
    id: "ollama",
    label: "Ollama (runs on this computer)",
    example: "llama3",
    keyless: true,
  },
];

/**
 * A sentence per failure. The reason codes are fixed strings chosen so nothing
 * from the OS or the filesystem reaches the renderer; they are not shown.
 */
const FAILURE_MESSAGES: Record<string, string> = {
  encryption_unavailable:
    "This computer cannot store a key securely, so LoopPlane will not save one. " +
    "On Linux this usually means no system keyring is running.",
  invalid_provider: "Choose a provider from the list.",
  invalid_model_id: "Enter the model id you want to use.",
  missing_key: "This provider needs an API key.",
  write_failed: "The key could not be saved. Check that there is free disk space.",
};

function optionFor(providerId: string): ProviderOption {
  return PROVIDERS.find((p) => p.id === providerId) ?? PROVIDERS[0]!;
}

export function ProviderSettings({ port }: { port: ProviderSettingsPort }) {
  const [stored, setStored] = useState<ProviderView | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [provider, setProvider] = useState("anthropic");
  const [modelId, setModelId] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const refresh = useCallback(async () => {
    const current = await port.get();
    setStored(current);
    if (current) {
      setProvider(current.provider);
      setModelId(current.modelId);
    }
    setLoaded(true);
  }, [port]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const option = optionFor(provider);
  const needsKey = !option.keyless;

  async function save(): Promise<void> {
    // The IPC boundary rejects a blank field outright rather than answering with
    // a reason, so check here first: otherwise an empty Model box produces a
    // rejected promise and a screen that silently does nothing.
    const trimmedModel = modelId.trim();
    const trimmedKey = apiKey.trim();
    if (!trimmedModel) {
      setFailure(FAILURE_MESSAGES.invalid_model_id!);
      return;
    }
    // A stored key is reused only for the same provider, so switching provider
    // with an empty box is a local failure, not a round trip.
    const reusable = Boolean(stored?.hasKey && stored.provider === provider);
    if (needsKey && !trimmedKey && !reusable) {
      setFailure(FAILURE_MESSAGES.missing_key!);
      return;
    }

    setBusy(true);
    setFailure(null);
    try {
      const result = await port.save({
        provider,
        modelId: trimmedModel,
        apiKey: needsKey ? trimmedKey || null : null,
      });
      if (result.ok) {
        setSaved(true);
        setApiKey("");
        await refresh();
        return;
      }
      setFailure(
        FAILURE_MESSAGES[result.reason] ??
          "The provider settings could not be saved.",
      );
    } catch {
      // A rejected invoke (stale handler, boundary validation) must still reach
      // the user; the rejection carries a fixed message key, never input text.
      setFailure("The provider settings could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  async function remove(): Promise<void> {
    setBusy(true);
    try {
      await port.clear();
      setSaved(true);
      setApiKey("");
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="provider-settings">
      <p className="provider-current">
        {!loaded
          ? "Checking…"
          : stored
            ? `Using ${optionFor(stored.provider).label} · ${stored.modelId}` +
              (stored.keyHint ? ` · key ${stored.keyHint}` : "")
            : "No provider is set up yet, so LoopPlane can only reply with a placeholder."}
      </p>

      <label className="provider-field">
        <span>Provider</span>
        <select
          value={provider}
          disabled={busy}
          onChange={(event) => {
            setProvider(event.target.value);
            setFailure(null);
          }}
        >
          {PROVIDERS.map((p) => (
            <option key={p.id} value={p.id}>
              {p.label}
            </option>
          ))}
        </select>
      </label>

      <label className="provider-field">
        <span>Model</span>
        <input
          type="text"
          value={modelId}
          disabled={busy}
          placeholder={option.example}
          onChange={(event) => setModelId(event.target.value)}
        />
      </label>

      {needsKey && (
        <label className="provider-field">
          <span>API key</span>
          <input
            type="password"
            value={apiKey}
            disabled={busy}
            autoComplete="off"
            placeholder={stored?.hasKey ? "Stored — type to replace" : ""}
            onChange={(event) => setApiKey(event.target.value)}
          />
        </label>
      )}

      {failure && (
        <p className="provider-failure" role="alert">
          {failure}
        </p>
      )}

      <div className="provider-actions">
        <button type="button" className="primary" disabled={busy} onClick={() => void save()}>
          Save
        </button>
        {stored && (
          <button type="button" disabled={busy} onClick={() => void remove()}>
            Remove
          </button>
        )}
      </div>

      {saved && (
        <p className="provider-restart" role="status">
          {/* Saving stores the key; it does not check that the provider accepts
              it. That only shows up on the first reply, so do not imply more. */}
          Saved. LoopPlane restarts to apply it, and the key is first checked
          when you send a message.{" "}
          <button type="button" disabled={busy} onClick={() => void port.restart()}>
            Restart LoopPlane
          </button>
        </p>
      )}

      <p className="provider-note" data-testid="provider-storage-note">
        The key stays on this computer, encrypted by the operating system. It is
        never sent anywhere except to the provider you chose, and it is excluded
        from LoopPlane backups.
      </p>
    </div>
  );
}
