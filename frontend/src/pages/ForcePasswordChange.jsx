import { useState } from "react";
import { api } from "../api/client";
import { useT } from "../i18n";
import "./Login.css";

// Feature #172 — vises i stedet for hele appen når user.must_change_password
// er sand (sat af en admin-nulstilling, feature #171). Jans udtrykkelige
// krav: "det skal være udfravigeligt". Selve håndhævelsen sidder i backend
// (api.deps.get_current_user blokerer alt andet) — denne skærm er blot
// UI-siden af samme regel, reuser Login.css's auth-screen/auth-card som
// PendingApproval.jsx allerede gør.
export default function ForcePasswordChange({ user, onPasswordChanged, onLogout }) {
  const t = useT();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.changeMyPassword(currentPassword, newPassword);
      // `POST /users/me/password` svarer 204 (intet indhold) — hent den
      // friske bruger igen for at få must_change_password: false med, samme
      // mønster som App.jsx's eget opstarts-kald til api.me().
      const updated = await api.me();
      onPasswordChanged(updated);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-screen">
      <div className="card auth-card">
        <div className="auth-brand">
          <span className="brand-mark" aria-hidden="true">
            🎬
          </span>
          {t("app.brand")}
        </div>

        <div className="banner banner-info">
          {t("account.mustChangePassword", { username: user.username })}
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          <label>
            {t("account.currentPassword")}
            <input
              type="password"
              autoComplete="current-password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              required
            />
          </label>
          <label>
            {t("account.newPassword")}
            <input
              type="password"
              autoComplete="new-password"
              // Feature #174 — se AccountSection's identiske note i
              // Settings.jsx: ingen klientside minLength, politikken er
              // admin-konfigurerbar og ikke læsbar herfra.
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
            />
          </label>

          {error && <div className="banner banner-error">{error}</div>}

          <button type="submit" className="btn btn-primary" disabled={submitting}>
            {t(submitting ? "common.saving" : "account.changePassword")}
          </button>
        </form>

        <button type="button" className="btn" onClick={onLogout}>
          {t("app.logout")}
        </button>
      </div>
    </div>
  );
}
