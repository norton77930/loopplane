import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { ApiClient, ApiError } from "../api/client";
import type { RawEvent } from "../api/types";
import { AppRoot } from "../AppRoot";

const TOKEN_KEY = "loopplane.token";

function stubClient(overrides: Partial<ApiClient> = {}): ApiClient {
  return {
    openSession: async () => ({ session_id: "s1" }),
    streamSession: async function* (): AsyncGenerator<RawEvent> {
      // no events
    },
    submit: async () => ({}),
    listSessions: async () => [],
    answerApproval: async () => undefined,
    answerQuestion: async () => undefined,
    cancel: async () => undefined,
    listModels: async () => [],
    uploadFile: async () => ({ reference: "r", name: "f" }),
    ...overrides,
  } as unknown as ApiClient;
}

beforeEach(() => sessionStorage.clear());

describe("AppRoot", () => {
  it("shows only the login screen when there is no token", () => {
    render(<AppRoot makeClient={() => stubClient()} />);

    expect(screen.getByLabelText("access token")).toBeInTheDocument();
    expect(screen.queryByLabelText("prompt")).not.toBeInTheDocument();
  });

  it("logs in with a token and shows the authenticated app", async () => {
    let captured: string | undefined;
    render(
      <AppRoot
        makeClient={(token) => {
          captured = token;
          return stubClient();
        }}
      />,
    );

    fireEvent.change(screen.getByLabelText("access token"), {
      target: { value: "tok-alice" },
    });
    fireEvent.click(screen.getByText("Log in"));

    expect(captured).toBe("tok-alice");
    expect(await screen.findByLabelText("prompt")).toBeInTheDocument();
    expect(screen.queryByLabelText("access token")).not.toBeInTheDocument();
  });

  it("stays logged in when a token is already stored for the tab", async () => {
    sessionStorage.setItem(TOKEN_KEY, "tok-stored");
    render(<AppRoot makeClient={() => stubClient()} />);

    expect(await screen.findByLabelText("prompt")).toBeInTheDocument();
  });

  it("logs out and clears the stored token", async () => {
    sessionStorage.setItem(TOKEN_KEY, "tok-stored");
    render(<AppRoot makeClient={() => stubClient()} />);

    await screen.findByLabelText("prompt");
    fireEvent.click(screen.getByText("Log out"));

    expect(screen.getByLabelText("access token")).toBeInTheDocument();
    expect(sessionStorage.getItem(TOKEN_KEY)).toBeNull();
  });

  it("returns to login on a 401 without leaking the token", async () => {
    sessionStorage.setItem(TOKEN_KEY, "tok-secret");
    render(
      <AppRoot
        makeClient={() =>
          stubClient({
            submit: async () => {
              throw new ApiError(401);
            },
          })
        }
      />,
    );

    fireEvent.change(screen.getByLabelText("prompt"), { target: { value: "hi" } });
    fireEvent.click(screen.getByText("Send"));

    await waitFor(() =>
      expect(screen.getByLabelText("access token")).toBeInTheDocument(),
    );
    expect(sessionStorage.getItem(TOKEN_KEY)).toBeNull();
    expect(document.body.textContent).not.toContain("tok-secret");
  });
});
