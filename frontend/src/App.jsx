import { useEffect, useState } from "react";
import Library from "./pages/Library";
import TvShows from "./pages/TvShows";
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
  const [tab, setTab] = useState("library");
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
  // a login check. No router library: this is the only route that needs
  // to exist outside the tab-based authenticated app, so a plain pathname
  // check is simpler than pulling in react-router for one page. Caddy's
  // `try_files {path} /index.html` (see DEPLOYMENT.md) and Vite's dev
  // server both already serve index.html for any unmatched path, so a
  // direct/shared link to /bio works without further server config.
  if (window.location.pathname.startsWith("/bio")) {
    return <CinemaPublic />;
  }

  if (user === undefined) {
    return null;
  }

  if (user === null) {
    return <Login onAuthenticated={setUser} />;
  }

  if (user.status !== "active") {
    return <PendingApproval user={user} onLogout={handleLogout} />;
  }

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
            <button
              className={tab === "wishlist" ? "active" : ""}
              onClick={() => setTab("wishlist")}
            >
              Ønsker
            </button>
            <button
              className={tab === "cinema" ? "active" : ""}
              onClick={() => setTab("cinema")}
            >
              🎬 Voldby BIO
            </button>
            <button
              className={tab === "print" ? "active" : ""}
              onClick={() => setTab("print")}
            >
              Print
            </button>
            <button
              className={tab === "stats" ? "active" : ""}
              onClick={() => setTab("stats")}
            >
              Statistik
            </button>
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
        {tab === "library" && <Library user={user} onSettingsChanged={setUser} />}
        {tab === "tv" && <TvShows user={user} onSettingsChanged={setUser} />}
        {tab === "wishlist" && <Library user={user} onSettingsChanged={setUser} wishlist />}
        {tab === "cinema" && <Cinema user={user} />}
        {tab === "print" && <PrintList />}
        {tab === "stats" && <Statistics />}
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
