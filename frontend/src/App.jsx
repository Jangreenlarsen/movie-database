import { useState } from "react";
import Library from "./pages/Library";
import ScanMovie from "./pages/ScanMovie";
import "./App.css";

function App() {
  const [tab, setTab] = useState("library");

  return (
    <div className="app">
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

      {tab === "library" ? <Library /> : <ScanMovie />}
    </div>
  );
}

export default App;
