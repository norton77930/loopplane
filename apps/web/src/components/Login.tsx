// The login screen: capture an access token for the unit-022 secured backend
// (login-auth-gate.md). The token is masked and an empty value is rejected.

import { useState } from "react";

export function Login({ onSubmit }: { onSubmit: (token: string) => void }) {
  const [value, setValue] = useState("");

  return (
    <form
      className="login"
      onSubmit={(event) => {
        event.preventDefault();
        const token = value.trim();
        if (token) onSubmit(token);
      }}
    >
      <h1>LoopPlane</h1>
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
      <button type="submit">Log in</button>
    </form>
  );
}
