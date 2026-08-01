import { useEffect, useState } from "react";
import Library from "./pages/Library";
import ScanMovie from "./pages/ScanMovie";
import TvShows from "./pages/TvShows";
import Settings from "./pages/Settings";
import PrintList from "./pages/PrintList";
import Statistics from "./pages/Statistics";
import Login from "./pages/Login";
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

  if (user === undefined) {
    return null;
  }

  if (user === null) {
    return <Login onAuthenticated={setUser} />;
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
              className={tab === "scan" ? "active" : ""}
              onClick={() => setTab("scan")}
            >
              Scan
            </button>
            <button
              className={tab === "wishlist" ? "active" : ""}
              onClick={() => setTab("wishlist")}
            >
              Ønsker
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
        {tab === "tv" && <TvShows user={user} />}
        {tab === "scan" && <ScanMovie user={user} />}
        {tab === "wishlist" && <Library user={user} onSettingsChanged={setUser} wishlist />}
        {tab === "print" && <PrintList />}
        {tab === "stats" && <Statistics />}
        {tab === "settings" && <Settings user={user} />}
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
