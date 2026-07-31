import { useEffect, useState } from "react";
import { api } from "../api/client";
import "./Settings.css";

export default function Settings({ user }) {
  const [status, setStatus] = useState("loading");
  const [startNumber, setStartNumber] = useState("");
  const [increment, setIncrement] = useState("");
  const [paddingWidth, setPaddingWidth] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    api
      .getSerialNumberConfig()
      .then((data) => {
        setStartNumber(String(data.start_number));
        setIncrement(String(data.increment));
        setPaddingWidth(String(data.padding_width));
        setStatus("ready");
      })
      .catch(() => setStatus("error"));
  }, []);

  async function save(event) {
    event.preventDefault();
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      const updated = await api.updateSerialNumberConfig({
        start_number: Number(startNumber),
        increment: Number(increment),
        padding_width: Number(paddingWidth),
      });
      setStartNumber(String(updated.start_number));
      setIncrement(String(updated.increment));
      setPaddingWidth(String(updated.padding_width));
      setSaved(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section>
      <div className="page-header">
        <h1>Indstillinger</h1>
      </div>

      <div className="card settings-account">
        <div className="modal-section-label">Konto</div>
        <p>
          Logget ind som <strong>{user.username}</strong>
        </p>
      </div>

      <div className="card settings-section">
        <h2>Serienummer-opsætning</h2>
        <p className="muted">
          Styrer hvilket nummer den næste tilføjede film får, og med hvilket spring
          fremtidige film nummereres. Vil du rette en <em>bestemt</em> films
          serienummer, gør du det i stedet i filmens redigeringsvindue i biblioteket.
        </p>

        {status === "loading" && <p className="muted">Indlæser...</p>}
        {status === "error" && (
          <div className="banner banner-error">Kunne ikke hente opsætning.</div>
        )}

        {status === "ready" && (
          <form className="serial-config-form" onSubmit={save}>
            <label>
              Næste film-nummer
              <input
                type="number"
                min="1"
                value={startNumber}
                onChange={(e) => setStartNumber(e.target.value)}
              />
            </label>
            <label>
              Spring (increment)
              <input
                type="number"
                min="1"
                value={increment}
                onChange={(e) => setIncrement(e.target.value)}
              />
            </label>
            <label>
              Antal cifre (foranstillede nuller)
              <input
                type="number"
                min="0"
                max="10"
                value={paddingWidth}
                onChange={(e) => setPaddingWidth(e.target.value)}
              />
            </label>

            {error && <div className="banner banner-error">{error}</div>}
            {saved && <div className="banner banner-info">Gemt!</div>}

            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? "Gemmer..." : "Gem"}
            </button>
          </form>
        )}
      </div>
    </section>
  );
}
