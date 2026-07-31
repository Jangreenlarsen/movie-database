import { useState } from "react";
import Library from "./pages/Library";
import ScanMovie from "./pages/ScanMovie";
import "./App.css";

function App() {
  const [tab, setTab] = useState("library");

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
          </nav>
        </div>
      </header>

      <main className="app-main">
        {tab === "library" ? <Library /> : <ScanMovie />}
      </main>
    </div>
  );
}

export default App;
