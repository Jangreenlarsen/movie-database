import { useState } from "react";
import { api } from "../api/client";
import { useT } from "../i18n";
import "./Login.css";

// Feature #205 — selvbetjent "glemt adgangskode": den side et token-link
// fra forgot-password-mailen peger på. Ingen login krævet (samme princip
// som /bio) — tokenet i URL'en ER selve legitimationen for denne ene
// handling.
export default function ResetPassword() {
  const t = useT();
  const token = new URLSearchParams(window.location.search).get("token");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);
    if (newPassword !== confirmPassword) {
      setError(t("resetPassword.mismatch"));
      return;
    }
    setSubmitting(true);
    try {
      await api.resetPassword(token, newPassword);
      setDone(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-screen">
      <div className="card auth-card">
        <div className="auth-header">
          <div className="auth-brand">
            <span className="brand-mark" aria-hidden="true">
              🎬
            </span>
            {t("app.brand")}
          </div>
        </div>

        <h2 style={{ margin: "0 0 4px" }}>{t("resetPassword.heading")}</h2>

        {!token ? (
          <div className="banner banner-error">{t("resetPassword.noToken")}</div>
        ) : done ? (
          <>
            <div className="banner banner-info">{t("resetPassword.success")}</div>
            <div className="auth-switch">
              <a href="/login">{t("auth.backToLogin")}</a>
            </div>
          </>
        ) : (
          <form className="auth-form" onSubmit={handleSubmit}>
            <label>
              {t("resetPassword.newPassword")}
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                autoComplete="new-password"
                required
              />
            </label>
            <label>
              {t("resetPassword.confirmPassword")}
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                autoComplete="new-password"
                required
              />
            </label>

            {error && <div className="banner banner-error">{error}</div>}

            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting ? t("auth.submitting") : t("resetPassword.submit")}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
