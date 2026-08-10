import { useEffect, useState } from "react";
import { api } from "../api/client";
import CinemaShowcase from "../components/CinemaShowcase";
import { formatShortDate, formatTime } from "../utils/cinemaFormat";
import LanguagePicker from "../components/LanguagePicker";
import { useLocale, useT } from "../i18n";
import "./CinemaPublic.css";
import "./Login.css";

// Feature #70 — public, no-login page at /bio. Read-only: no admin tools,
// no "ønsk visning"/anmeldelses-knapper, just the showcase section + the
// upcoming program. Deliberately a separate component from Cinema.jsx
// rather than a "publicOnly" prop on it — Cinema.jsx assumes a logged-in
// `user` throughout (role checks, screening-request actions), and keeping
// the public route as its own simple component avoids having to thread a
// "no user" case through all of that.
//
// v2 (Jans feedback 2026-08-03): "Om Voldby BIO" moved back above the
// program, and every upcoming screening now sits in one flat side-by-side
// poster grid instead of being grouped under full per-day headings — with
// mostly one screening per day, date-grouping just produced a long single
// column of near-empty rows.
export default function CinemaPublic({ user = null, language, onLanguageChange }) {
  const t = useT();
  // BUGS.md #53 — åben/lukket-tilstanden ligger her frem for i
  // PublicLoginToggle, fordi knappen og panelet nu står to forskellige
  // steder i træet.
  const [loginOpen, setLoginOpen] = useState(false);
  const [screenings, setScreenings] = useState([]);
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    api
      .listScreenings(true)
      .then((data) => {
        setScreenings(data);
        setStatus("ready");
      })
      .catch(() => setStatus("error"));
  }, []);

  return (
    <div className="cinema-public-page">
      <header className="cinema-public-hero">
        {/* Feature #99 — sprogvalget står ved siden af login-knappen, ikke i
            modsatte hjørne: de to hører sammen som "det du gør før du er
            logget ind", og var visuelt afkoblet da de stod hver sit sted.
            Login-knappen står først (Jans ønske 2026-08-09).

            BUGS.md #53 — kun *knappen* hører til i gruppen. Selve
            login-panelet er en søskende, fordi gruppen er absolut placeret:
            lå panelet indeni, ville dets egen absolutte placering og
            `max-width: calc(100% - 40px)` regne mod gruppens få pixels i
            stedet for mod hero-området, og panelet blev mast sammen. */}
        <div className="cinema-public-hero-actions">
          <PublicLoginToggle user={user} open={loginOpen} onToggle={() => setLoginOpen((v) => !v)} />
          {onLanguageChange && (
            <LanguagePicker language={language} onChange={onLanguageChange} />
          )}
        </div>
        {loginOpen && !user && (
          <PublicLoginPanel language={language} onClose={() => setLoginOpen(false)} />
        )}
        {/* Feature #104 — Voldby BIOs eget skilt som topbillede, i stedet for
            en tekst-overskrift på en accent-gradient. `<h1>` ombryder
            billedet frem for at stå separat: en skærmlæser skal stadig have
            en rigtig overskrift, og alt-teksten på billedet giver den —
            uden behov for en visuelt skjult duplikat-tekst ved siden af. */}
        <h1 className="cinema-public-sign">
          <img src="/cinema/voldby-bio-sign.jpg" alt={t("public.signAlt")} />
        </h1>
        <p className="cinema-public-tagline">{t("public.tagline")}</p>
      </header>

      <main className="cinema-public-main">
        <section>
          <h2 className="cinema-public-section-heading">{t("public.about")}</h2>
          <CinemaShowcase />
        </section>

        <section>
          <h2 className="cinema-public-section-heading">{t("public.nowShowing")}</h2>
          {status === "loading" && <p className="muted">{t("cinema.loadingProgram")}</p>}
          {status === "error" && (
            <div className="banner banner-error">{t("cinema.programLoadError")}</div>
          )}
          {status === "ready" && screenings.length === 0 && (
            <p className="muted">{t("cinema.noScreenings")}</p>
          )}

          {screenings.length > 0 && (
            <div className="bio-poster-grid">
              {screenings.map((screening) => (
                <PublicScreeningCard key={screening.id} screening={screening} />
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

// Feature #82 — Jans ønske: en besøgende på den delte, ikke-autentificerede
// /bio-side skal kunne logge ind direkte her i stedet for selv at skulle
// vide at navigere til "/". Et vellykket login sender browseren til "/"
// med en rigtig navigation (appen har ingen router og bruger allerede en
// ren pathname-check for /bio, jf. kommentaren i App.jsx) — der tager
// App.jsx over med den nu autentificerede bruger, landet på Voldby BIO
// (samme feature #82's anden halvdel: login lander altid der).
//
// BUGS.md #53 — knappen og selve panelet er to komponenter, fordi de skal
// stå to forskellige steder i træet: knappen sammen med sprogvalget i den
// absolut placerede hjørne-gruppe, panelet som søskende direkte i hero'en,
// hvor det kan få sin egen bredde.
function PublicLoginToggle({ user, open, onToggle }) {
  const t = useT();

  // Feature #84 — someone already signed in shouldn't be offered a login
  // form on what is now also the site's front page; send them into the app
  // instead. `user` is `undefined` while the session check is still in
  // flight, which correctly falls through to the login badge — the public
  // page must never block on that lookup (see App.jsx), and the badge
  // simply upgrades itself once the session resolves.
  if (user) {
    return (
      <a className="cinema-public-login-toggle" href="/">
        {t("public.openLibrary")}
      </a>
    );
  }

  // Knappen bliver stående mens panelet er åbent — dels så hjørne-gruppen
  // ikke skifter bredde og rykker sprogvalget rundt, dels så den kan lukke
  // panelet igen.
  return (
    <button
      type="button"
      className={`cinema-public-login-toggle${open ? " active" : ""}`}
      onClick={onToggle}
      aria-expanded={open}
    >
      {t("auth.login")}
    </button>
  );
}

function PublicLoginPanel({ language, onClose }) {
  const t = useT();
  // Feature #83 — samme to-tilstands-mønster som appens egen Login.jsx, så
  // en besøgende der har fået biograf-linket delt også kan oprette sin konto
  // her i stedet for først at skulle finde appens forside.
  const [mode, setMode] = useState("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  function switchMode(nextMode) {
    setMode(nextMode);
    setError(null);
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (mode === "login") {
        await api.login(username, password);
      } else {
        // Nye konti er `pending` (feature #66) — App.jsx viser så
        // "afventer godkendelse"-siden efter navigationen, præcis som når
        // man registrerer fra forsiden. Derfor samme redirect i begge
        // tilstande frem for en særskilt kvitteringsbesked her.
        // Feature #97 — se den identiske note i Login.jsx.
        await api.register(username, password, language);
      }
      window.location.assign("/");
    } catch (err) {
      setError(err.message);
      setSubmitting(false);
    }
  }

  return (
    <div className="cinema-public-login-panel">
      <form className="auth-form" onSubmit={handleSubmit}>
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
            autoFocus
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
        <div className="cinema-public-login-actions">
          <button type="button" className="btn" onClick={onClose} disabled={submitting}>
            {t("common.cancel")}
          </button>
          <button type="submit" className="btn btn-primary" disabled={submitting}>
            {t(
              submitting
                ? mode === "login"
                  ? "public.loggingIn"
                  : "public.creating"
                : mode === "login"
                  ? "auth.login"
                  : "public.createUser"
            )}
          </button>
        </div>
        <div className="auth-switch">
          {mode === "login" ? (
            <>
              {t("auth.noAccount")}{" "}
              <button type="button" onClick={() => switchMode("register")}>
                {t("public.createUser")}
              </button>
            </>
          ) : (
            <>
              {t("auth.haveAccount")}{" "}
              <button type="button" onClick={() => switchMode("login")}>
                {t("auth.login")}
              </button>
            </>
          )}
        </div>
      </form>
    </div>
  );
}

function PublicScreeningCard({ screening }) {
  const t = useT();
  const locale = useLocale();
  return (
    <div className="bio-poster-card">
      <div className="bio-poster-card-datetime">
        {formatShortDate(screening.scheduled_at, locale)} ·{" "}
        {formatTime(screening.scheduled_at, locale)}
      </div>
      <div className="bio-poster-card-poster">
        {screening.poster_url ? (
          <img src={screening.poster_url} alt={screening.title ?? ""} loading="lazy" />
        ) : (
          <span>{screening.media_kind === "movie" ? "🎬" : "📺"}</span>
        )}
      </div>
      <div className="bio-poster-card-body">
        <h3 className="bio-poster-card-title">
          {screening.title ?? t("cinema.unknownTitle")}
          {screening.year ? ` (${screening.year})` : ""}
        </h3>
        {screening.genres?.length > 0 && (
          <div className="bio-poster-card-genres">{screening.genres.join(", ")}</div>
        )}
      </div>
    </div>
  );
}
