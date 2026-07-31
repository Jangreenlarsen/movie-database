import { useState } from "react";
import { api } from "../api/client";
import "./Login.css";

export default function Login({ onAuthenticated }) {
  const [mode, setMode] = useState("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
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
          : await api.register(username, password);
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
        <div className="auth-brand">
          <span className="brand-mark" aria-hidden="true">
            🎬
          </span>
          Filmbibliotek
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          <label>
            Brugernavn
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              required
            />
          </label>
          <label>
            Adgangskode
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
              ? "Vent venligst..."
              : mode === "login"
                ? "Log ind"
                : "Opret konto"}
          </button>
        </form>

        <div className="auth-switch">
          {mode === "login" ? (
            <>
              Ingen konto?{" "}
              <button type="button" onClick={() => setMode("register")}>
                Opret en
              </button>
            </>
          ) : (
            <>
              Har du allerede en konto?{" "}
              <button type="button" onClick={() => setMode("login")}>
                Log ind
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
