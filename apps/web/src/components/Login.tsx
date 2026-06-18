// The login screen: capture an access token for the unit-022 secured backend
// (login-auth-gate.md). Restyled (025) as a centered themed card; the token stays masked and
// an empty value is rejected — the 023 behavior is unchanged.

import { useState } from "react";

import { useTranslation } from "../i18n/i18n";

export function Login({ onSubmit }: { onSubmit: (token: string) => void }) {
  const [value, setValue] = useState("");
  const { t } = useTranslation();

  return (
    <div className="login-screen">
      <div className="login-card">
        <h1>LoopPlane</h1>
        <p>{t("login.subtitle")}</p>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            const token = value.trim();
            if (token) onSubmit(token);
          }}
        >
          <label className="login-field">
            {t("login.token")}
            <input
              aria-label="access token"
              type="password"
              autoComplete="off"
              value={value}
              onChange={(event) => setValue(event.target.value)}
            />
          </label>
          <button type="submit" className="primary">
            {t("login.submit")}
          </button>
        </form>
      </div>
    </div>
  );
}
