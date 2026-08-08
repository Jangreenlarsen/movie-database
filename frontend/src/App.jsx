import { useEffect, useState } from "react";
import Library from "./pages/Library";
import TvShows from "./pages/TvShows";
import Wishlist from "./pages/Wishlist";
import Settings from "./pages/Settings";
import PrintList from "./pages/PrintList";
import Statistics from "./pages/Statistics";
import Cinema from "./pages/Cinema";
import CinemaPublic from "./pages/CinemaPublic";
import Login from "./pages/Login";
import PendingApproval from "./pages/PendingApproval";
import { api } from "./api/client";
import "./App.css";

function App() {
  // Jans ønske 2026-08-04: efter login lander man på Voldby BIO i stedet
  // for filmbiblioteket — gælder både et frisk login og en genindlæst side
  // med en allerede gyldig session, da begge ender her.
  const [tab, setTab] = useState("cinema");
  const [user, setUser] = useState(undefined); // undefined = checking, null = logged out
  const [versionInfo, setVersionInfo] = useState(null);

  useEffect(() => {
    api
      .me()
      .then(setUser)
      .catch(() => setUser(null));
    api
      .health()
      .then((data) => setVersionInfo({ version: data.version, build: data.build }))
      .catch(() => {});
  }, []);

  async function handleLogout() {
    await api.logout();
    setUser(null);
  }

  // Feature #70 — /bio is a public, no-login page (shareable outside the
  // app), checked before any auth state so it never waits on or requires
  // a login check. No router library: these are the only routes that need
  // to exist outside the tab-based authenticated app, so plain pathname
  // checks are simpler than pulling in react-router. Caddy's
  // `try_files {path} /index.html` (see DEPLOYMENT.md) and Vite's dev
  // server both already serve index.html for any unmatched path, so a
  // direct/shared link works without further server config.
  //
  // `user` is passed through (possibly still `undefined` while the session
  // check is in flight) purely so the login badge can offer "Åbn
  // biblioteket" to someone already signed in — the page itself renders
  // immediately either way, which is the whole point of this early return.
  if (window.location.pathname.startsWith("/bio")) {
    return <CinemaPublic user={user} />;
  }

  // Feature #84 — the full login page keeps its own URL so it isn't
  // orphaned by the landing-page change below, and so there's still a
  // direct link for "just let me sign in".
  if (window.location.pathname.startsWith("/login")) {
    return <Login onAuthenticated={setUser} />;
  }

  if (user === undefined) {
    return null;
  }

  // Feature #84 — Voldby BIO is the public front door: a logged-out visitor
  // to "/" gets the cinema page (programme, showcase, and the login/opret
  // badge) rather than a bare login form, so the shared /bio link and the
  // site root are the same shop window.
  if (user === null) {
    return <CinemaPublic user={null} />;
  }

  if (user.status !== "active") {
    return <PendingApproval user={user} onLogout={handleLogout} />;
  }

  // Feature #72 — guest is read-only: Ønsker/Print/Statistik all involve
  // either writing (ønske en film) or aren't part of "se film/TV-bibliotek",
  // so they're hidden entirely rather than just disabled.
  const isGuest = user.role === "guest";

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-header-inner">
          <div className="brand">
            <span className="brand-mark" aria-hidden="true">
              🎬
            </span>
            Film &amp; TV-bibliotek
          </div>
          <nav className="tabs">
            <button
              className={tab === "library" ? "active" : ""}
              onClick={() => setTab("library")}
            >
              Film
            </button>
            <button
              className={tab === "tv" ? "active" : ""}
              onClick={() => setTab("tv")}
            >
              TV-serier
            </button>
            {!isGuest && (
              <button
                className={tab === "wishlist" ? "active" : ""}
                onClick={() => setTab("wishlist")}
              >
                Ønsker
              </button>
            )}
            <button
              className={tab === "cinema" ? "active" : ""}
              onClick={() => setTab("cinema")}
            >
              🎬 Voldby BIO
            </button>
            {!isGuest && (
              <button
                className={tab === "print" ? "active" : ""}
                onClick={() => setTab("print")}
              >
                Print
              </button>
            )}
            {!isGuest && (
              <button
                className={tab === "stats" ? "active" : ""}
                onClick={() => setTab("stats")}
              >
                Statistik
              </button>
            )}
            <button
              className={tab === "settings" ? "active" : ""}
              onClick={() => setTab("settings")}
            >
              Indstillinger
            </button>
          </nav>
          <div className="header-user">
            <span className="muted">{user.username}</span>
            <button type="button" className="btn" onClick={handleLogout}>
              Log ud
            </button>
          </div>
        </div>
      </header>

      <main className="app-main">
        {tab === "library" && (
          <Library user={user} onSettingsChanged={setUser} onGoToTvShows={() => setTab("tv")} />
        )}
        {tab === "tv" && (
          <TvShows user={user} onSettingsChanged={setUser} onGoToMovies={() => setTab("library")} />
        )}
        {!isGuest && tab === "wishlist" && <Wishlist user={user} onSettingsChanged={setUser} />}
        {tab === "cinema" && <Cinema user={user} />}
        {!isGuest && tab === "print" && <PrintList />}
        {!isGuest && tab === "stats" && <Statistics />}
        {tab === "settings" && <Settings user={user} onSettingsChanged={setUser} />}
      </main>

      <footer className="app-footer">
        <span className="muted">
          {versionInfo ? `v${versionInfo.version} (build ${versionInfo.build})` : ""}
        </span>
      </footer>
    </div>
  );
}

export default App;
