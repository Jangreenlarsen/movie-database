import { useEffect, useState } from "react";
import Library from "./pages/Library";
import ScanMovie from "./pages/ScanMovie";
import Settings from "./pages/Settings";
import Login from "./pages/Login";
import { api } from "./api/client";
import "./App.css";

function App() {
  const [tab, setTab] = useState("library");
  const [user, setUser] = useState(undefined); // undefined = checking, null = logged out

  useEffect(() => {
    api
      .me()
      .then(setUser)
      .catch(() => setUser(null));
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
            Filmbibliotek
          </div>
          <nav className="tabs">
            <button
              className={tab === "library" ? "active" : ""}
              onClick={() => setTab("library")}
            >
              Bibliotek
            </button>
            <button
              className={tab === "scan" ? "active" : ""}
              onClick={() => setTab("scan")}
            >
              Scan film
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
        {tab === "scan" && <ScanMovie />}
        {tab === "settings" && <Settings user={user} />}
      </main>
    </div>
  );
}

export default App;
