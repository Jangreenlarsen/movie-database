import { useState } from "react";
import { api } from "../api/client";
import LanguagePicker from "../components/LanguagePicker";
import { useT } from "../i18n";
import "./Login.css";

export default function Login({ onAuthenticated, language, onLanguageChange }) {
  const t = useT();
  const [mode, setMode] = useState("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const user =
        mode === "login"
          ? await api.login(username, password)
          // Feature #97 — sprogvalget følger med, så en ny konto starter på
          // det sprog brugeren allerede har valgt her. Feature #140 — fuldt navn.
          : await api.register(username, password, language, fullName);
      onAuthenticated(user);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-screen">
      <div className="card auth-card">
        {/* Feature #99 — vælgeren står på linje med logoet i toppen af
            login-kortet, samme relative plads som på den offentlige BIO-side,
            så den sidder samme sted uanset hvilken vej man kom ind. */}
        <div className="auth-header">
          <div className="auth-brand">
            <span className="brand-mark" aria-hidden="true">
              🎬
            </span>
            {t("app.brand")}
          </div>
          {onLanguageChange && (
            <LanguagePicker language={language} onChange={onLanguageChange} />
          )}
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          {/* Feature #140 — obligatorisk fuldt navn ved oprettelse, så en admin
              kan se hvem der beder om adgang. Vises kun i opret-tilstand. */}
          {mode === "register" && (
            <label>
              {t("auth.fullName")}
              <input
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                autoComplete="name"
                placeholder={t("auth.fullNamePlaceholder")}
                required
              />
            </label>
          )}
          <label>
            {t("auth.username")}
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              autoCapitalize="off"
              autoCorrect="off"
              spellCheck={false}
              required
            />
          </label>
          <label>
            {t("auth.password")}
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              minLength={mode === "register" ? 8 : undefined}
              required
            />
          </label>

          {error && <div className="banner banner-error">{error}</div>}

          <button type="submit" className="btn btn-primary" disabled={submitting}>
            {submitting
              ? t("auth.submitting")
              : mode === "login"
                ? t("auth.login")
                : t("auth.register")}
          </button>
        </form>

        <div className="auth-switch">
          {mode === "login" ? (
            <>
              {t("auth.noAccount")}{" "}
              <button type="button" onClick={() => setMode("register")}>
                {t("auth.createOne")}
              </button>
            </>
          ) : (
            <>
              {t("auth.haveAccount")}{" "}
              <button type="button" onClick={() => setMode("login")}>
                {t("auth.login")}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
