// The login screen: capture an access token for the unit-022 secured backend
// (login-auth-gate.md). Restyled (025) as a centered themed card; the token stays masked and
// an empty value is rejected — the 023 behavior is unchanged.

import { useState } from "react";

export function Login({ onSubmit }: { onSubmit: (token: string) => void }) {
  const [value, setValue] = useState("");

  return (
    <div className="login-screen">
      <div className="login-card">
        <h1>LoopPlane</h1>
        <p>Sign in with your access token to continue.</p>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            const token = value.trim();
            if (token) onSubmit(token);
          }}
        >
          <label className="login-field">
            Access token
            <input
              aria-label="access token"
              type="password"
              autoComplete="off"
              value={value}
              onChange={(event) => setValue(event.target.value)}
            />
          </label>
          <button type="submit" className="primary">
            Log in
          </button>
        </form>
      </div>
    </div>
  );
}
