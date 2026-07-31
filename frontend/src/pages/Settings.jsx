import { useEffect, useState } from "react";
import { api } from "../api/client";
import "./Settings.css";

export default function Settings({ user }) {
  const isAdmin = user.role === "admin";

  return (
    <section>
      <div className="page-header">
        <h1>Indstillinger</h1>
      </div>

      <AccountSection user={user} />
      <SerialNumberSection isAdmin={isAdmin} />
      {isAdmin && <UsersSection currentUserId={user.id} />}
    </section>
  );
}

function AccountSection({ user }) {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(null);

  async function changePassword(event) {
    event.preventDefault();
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      await api.changeMyPassword(currentPassword, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      setSaved(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="card settings-account">
      <div className="modal-section-label">Konto</div>
      <p>
        Logget ind som <strong>{user.username}</strong>{" "}
        <span className="role-badge">{user.role === "admin" ? "Admin" : "Standard"}</span>
      </p>

      <form className="serial-config-form" onSubmit={changePassword}>
        <label>
          Nuværende adgangskode
          <input
            type="password"
            autoComplete="current-password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            required
          />
        </label>
        <label>
          Ny adgangskode
          <input
            type="password"
            autoComplete="new-password"
            minLength={8}
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            required
          />
        </label>

        {error && <div className="banner banner-error">{error}</div>}
        {saved && <div className="banner banner-info">Adgangskode ændret!</div>}

        <button type="submit" className="btn btn-primary" disabled={saving}>
          {saving ? "Gemmer..." : "Skift adgangskode"}
        </button>
      </form>
    </div>
  );
}

function SerialNumberSection({ isAdmin }) {
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
    <div className="card settings-section">
      <h2>Serienummer-opsætning</h2>
      <p className="muted">
        Styrer hvilket nummer den næste tilføjede film får, og med hvilket spring
        fremtidige film nummereres. Vil du rette en <em>bestemt</em> films
        serienummer, gør du det i stedet i filmens redigeringsvindue i biblioteket.
        {!isAdmin && " Kun administratorer kan ændre denne opsætning."}
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
              disabled={!isAdmin}
              value={startNumber}
              onChange={(e) => setStartNumber(e.target.value)}
            />
          </label>
          <label>
            Spring (increment)
            <input
              type="number"
              min="1"
              disabled={!isAdmin}
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
              disabled={!isAdmin}
              value={paddingWidth}
              onChange={(e) => setPaddingWidth(e.target.value)}
            />
          </label>

          {error && <div className="banner banner-error">{error}</div>}
          {saved && <div className="banner banner-info">Gemt!</div>}

          {isAdmin && (
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? "Gemmer..." : "Gem"}
            </button>
          )}
        </form>
      )}
    </div>
  );
}

function UsersSection({ currentUserId }) {
  const [users, setUsers] = useState([]);
  const [status, setStatus] = useState("loading");
  const [updatingId, setUpdatingId] = useState(null);

  function load() {
    setStatus("loading");
    api
      .listUsers()
      .then((data) => {
        setUsers(data);
        setStatus("ready");
      })
      .catch(() => setStatus("error"));
  }

  useEffect(load, []);

  async function toggleRole(targetUser) {
    const nextRole = targetUser.role === "admin" ? "standard" : "admin";
    setUpdatingId(targetUser.id);
    try {
      await api.updateUserRole(targetUser.id, nextRole);
      load();
    } finally {
      setUpdatingId(null);
    }
  }

  return (
    <div className="card settings-section">
      <h2>Brugere</h2>
      <p className="muted">Administrér hvem der har admin-rettigheder.</p>

      {status === "loading" && <p className="muted">Indlæser...</p>}
      {status === "error" && (
        <div className="banner banner-error">Kunne ikke hente brugere.</div>
      )}

      {status === "ready" && (
        <ul className="user-list">
          {users.map((u) => (
            <li key={u.id} className="user-row">
              <span className="user-row-name">
                {u.username}
                {u.id === currentUserId && <span className="muted"> (dig)</span>}
              </span>
              <span className="role-badge">{u.role === "admin" ? "Admin" : "Standard"}</span>
              <button
                type="button"
                className="btn"
                disabled={u.id === currentUserId || updatingId === u.id}
                onClick={() => toggleRole(u)}
              >
                {updatingId === u.id
                  ? "Opdaterer..."
                  : u.role === "admin"
                    ? "Fjern admin"
                    : "Gør til admin"}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
