// The auth gate over the unit-018 app (login-auth-gate.md): no token -> Login;
// token -> the authenticated App wired with a token-carrying client. The token is
// persisted in sessionStorage (survives a reload within the tab, cleared on close);
// logout and a 401 clear it. `makeClient` is injectable so tests stub the network.

import { useMemo, useState } from "react";

import { ApiClient } from "./api/client";
import { App } from "./App";
import { Login } from "./components/Login";

const TOKEN_KEY = "loopplane.token";

function defaultMakeClient(token: string): ApiClient {
  return new ApiClient({ authHeader: `Bearer ${token}` });
}

export function AppRoot({
  makeClient = defaultMakeClient,
}: {
  makeClient?: (token: string) => ApiClient;
} = {}) {
  const [token, setToken] = useState<string | null>(() =>
    sessionStorage.getItem(TOKEN_KEY),
  );
  const client = useMemo(
    () => (token === null ? null : makeClient(token)),
    [token, makeClient],
  );

  function login(next: string) {
    sessionStorage.setItem(TOKEN_KEY, next);
    setToken(next);
  }

  function logout() {
    sessionStorage.removeItem(TOKEN_KEY);
    setToken(null);
  }

  if (token === null || client === null) {
    return <Login onSubmit={login} />;
  }

  return (
    <div className="authed">
      <button type="button" className="logout" onClick={logout}>
        Log out
      </button>
      <App client={client} onUnauthorized={logout} />
    </div>
  );
}
