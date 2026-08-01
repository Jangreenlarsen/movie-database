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
      <DeletedMoviesSection />
      {isAdmin && <TmdbSyncSection />}
      {isAdmin && <SystemSettingsSection />}
      {isAdmin && <DeploySection />}
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

function DeletedMoviesSection() {
  const [entries, setEntries] = useState([]);
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    api
      .listDeletedMovies()
      .then((data) => {
        setEntries(data);
        setStatus("ready");
      })
      .catch(() => setStatus("error"));
  }, []);

  return (
    <div className="card settings-section">
      <h2>Slettede film</h2>
      <p className="muted">
        Når en film slettes, logges den her sammen med serienummeret — nummeret er
        derefter frit til at blive genbrugt af en ny film.
      </p>

      {status === "loading" && <p className="muted">Indlæser...</p>}
      {status === "error" && (
        <div className="banner banner-error">Kunne ikke hente slettede film.</div>
      )}

      {status === "ready" && entries.length === 0 && (
        <p className="muted">Ingen film er slettet endnu.</p>
      )}

      {status === "ready" && entries.length > 0 && (
        <ul className="user-list">
          {entries.map((entry) => (
            <li key={entry.id} className="user-row">
              <span className="user-row-name">
                #{entry.serial_number ?? "—"} · {entry.title}
                {entry.year ? ` (${entry.year})` : ""}
              </span>
              <span className="muted">
                Slettet af {entry.deleted_by ?? "ukendt"} d.{" "}
                {new Date(entry.deleted_at).toLocaleDateString("da-DK")}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function TmdbSyncSection() {
  const [status, setStatus] = useState("idle");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  async function sync() {
    setStatus("syncing");
    setError(null);
    setResult(null);
    try {
      const data = await api.syncMoviesFromTmdb();
      setResult(data);
      setStatus("done");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }

  return (
    <div className="card settings-section">
      <h2>TMDb-synkronisering</h2>
      <p className="muted">
        Henter frisk metadata (titel, år, poster, plot, genrer, medvirkende, rating,
        spilletid) fra TMDb for alle film der er oprettet via TMDb, og opdaterer det
        lokalt gemte. Dine egne oplysninger (tags, format, lyd-type, lokation, ejer,
        serienummer) rører den ikke. Kan tage et øjeblik afhængig af antal film.
      </p>

      <button type="button" className="btn btn-primary" onClick={sync} disabled={status === "syncing"}>
        {status === "syncing" ? "Synkroniserer..." : "Opdatér alle film fra TMDb"}
      </button>

      {status === "error" && (
        <div className="banner banner-error" style={{ marginTop: 12 }}>
          {error}
        </div>
      )}

      {status === "done" && result && (
        <div
          className={`banner ${result.stopped_early ? "banner-error" : "banner-info"}`}
          style={{ marginTop: 12 }}
        >
          {result.stopped_early ? (
            result.synced === 0 && result.total === result.failed && result.failed > 0 ? (
              <>Synkronisering afbrudt — tjek at backend har en gyldig TMDB_API_TOKEN.</>
            ) : (
              <>
                {result.synced} af {result.total} film opdateret, men stoppet tidligt fordi TMDb
                ramte et rate-limit. Prøv igen om lidt for at opdatere resten.
              </>
            )
          ) : (
            <>
              {result.synced} af {result.total} film opdateret.
              {result.failed > 0 &&
                ` ${result.failed} kunne ikke hentes: ${result.failed_titles.join(", ")}.`}
            </>
          )}
        </div>
      )}
    </div>
  );
}

function SystemSettingsSection() {
  const [statusData, setStatusData] = useState(null);
  const [loadStatus, setLoadStatus] = useState("loading");

  function load() {
    setLoadStatus("loading");
    api
      .getSystemSettings()
      .then((data) => {
        setStatusData(data);
        setLoadStatus("ready");
      })
      .catch(() => setLoadStatus("error"));
  }

  useEffect(load, []);

  return (
    <div className="card settings-section">
      <h2>System-indstillinger</h2>
      <p className="muted">
        Eksterne API-nøgler og Plex-integration. Kan i stedet sættes via <code>.env</code> på
        serveren — en værdi sat her overstyrer den, med det samme, uden genstart. Nøgler vises
        aldrig igen efter de er gemt, kun om en nøgle er sat og hvorfra. Plex-server-URL'en er
        undtagelsen — den er ikke en hemmelighed, og vises derfor med sin faktiske værdi.
      </p>

      {loadStatus === "loading" && <p className="muted">Indlæser...</p>}
      {loadStatus === "error" && (
        <div className="banner banner-error">Kunne ikke hente status.</div>
      )}

      {loadStatus === "ready" && statusData && (
        <>
          <ApiKeyRow
            label="TMDb API-token"
            field="tmdb_api_token"
            status={statusData.tmdb_api_token}
            onSaved={load}
          />
          <ApiKeyRow
            label="UPC API-nøgle"
            field="upc_api_key"
            status={statusData.upc_api_key}
            onSaved={load}
          />
          <ApiKeyRow
            label="Discogs-token"
            field="discogs_token"
            status={statusData.discogs_token}
            onSaved={load}
          />
          <ApiKeyRow
            label="OMDb API-nøgle"
            field="omdb_api_key"
            status={statusData.omdb_api_key}
            onSaved={load}
          />
          <PlainSettingRow
            label="Plex-server-URL"
            field="plex_server_url"
            hint="Ikke en hemmelighed — vises som den er, fx http://192.168.1.50:32400"
            currentValue={statusData.plex_server_url}
            onSaved={load}
          />
          <ApiKeyRow
            label="Plex-token"
            field="plex_token"
            status={statusData.plex_token}
            onSaved={load}
          />
        </>
      )}
    </div>
  );
}

function PlainSettingRow({ label, field, hint, currentValue, onSaved }) {
  const [value, setValue] = useState(currentValue ?? "");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    setValue(currentValue ?? "");
  }, [currentValue]);

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await api.updateSystemSettings({ [field]: value });
      setSaved(true);
      onSaved();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="serial-config-form" style={{ marginBottom: 16 }} onSubmit={submit}>
      <label>
        {label} — <span className="muted">{hint}</span>
        <input value={value} onChange={(e) => setValue(e.target.value)} style={{ width: "100%" }} />
      </label>

      {error && <div className="banner banner-error">{error}</div>}
      {saved && <div className="banner banner-info">Gemt!</div>}

      <button type="submit" className="btn btn-primary" disabled={saving}>
        {saving ? "Gemmer..." : "Gem"}
      </button>
    </form>
  );
}

function ApiKeyRow({ label, field, status, onSaved }) {
  const [value, setValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(null);

  async function submit(newValue) {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await api.updateSystemSettings({ [field]: newValue });
      setValue("");
      setSaved(true);
      onSaved();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  const sourceLabel =
    status.source === "custom"
      ? "Sat her i UI'et"
      : status.source === "env"
        ? "Sat via .env på serveren"
        : "Ikke sat";

  return (
    <form
      className="serial-config-form"
      style={{ marginBottom: 16 }}
      onSubmit={(event) => {
        event.preventDefault();
        if (value) submit(value);
      }}
    >
      <label>
        {label} — <span className="muted">{sourceLabel}</span>
        <input
          type="password"
          autoComplete="off"
          placeholder={status.configured ? "•••••••• (indtast for at ændre)" : "Indtast nøgle"}
          value={value}
          onChange={(e) => setValue(e.target.value)}
        />
      </label>

      {error && <div className="banner banner-error">{error}</div>}
      {saved && <div className="banner banner-info">Gemt!</div>}

      <div style={{ display: "flex", gap: 8 }}>
        <button type="submit" className="btn btn-primary" disabled={saving || !value}>
          {saving ? "Gemmer..." : "Gem"}
        </button>
        {status.source === "custom" && (
          <button type="button" className="btn" onClick={() => submit("")} disabled={saving}>
            Ryd (brug .env igen)
          </button>
        )}
      </div>
    </form>
  );
}

function DeploySection() {
  const [currentBuild, setCurrentBuild] = useState(null);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState(null);

  useEffect(() => {
    api
      .health()
      .then((data) => setCurrentBuild(data.build))
      .catch(() => {});
  }, []);

  async function deploy() {
    setStatus("deploying");
    setError(null);
    const startedFromBuild = currentBuild;

    try {
      await api.triggerDeploy();
    } catch (err) {
      setError(err.message);
      setStatus("error");
      return;
    }

    const deadline = Date.now() + 120_000;
    const poll = setInterval(async () => {
      if (Date.now() > deadline) {
        clearInterval(poll);
        setStatus("timeout");
        return;
      }
      try {
        const data = await api.health();
        if (data.build !== startedFromBuild) {
          clearInterval(poll);
          setCurrentBuild(data.build);
          setStatus("done");
        }
      } catch {
        // Backend er nede et øjeblik mens den genstarter — bliv ved med at prøve.
      }
    }, 3000);
  }

  return (
    <div className="card settings-section">
      <h2>Opdatér fra GitHub</h2>
      <p className="muted">
        Henter seneste version fra GitHub (main-branchen), geninstallerer afhængigheder og
        genstarter serveren automatisk. Kun tilgængelig i produktion (se DEPLOYMENT.md). Tager
        typisk et minuts tid — siden er kortvarigt utilgængelig mens backend genstarter.
        {currentBuild && <> Kører nu build {currentBuild}.</>}
      </p>

      <button
        type="button"
        className="btn btn-primary"
        onClick={deploy}
        disabled={status === "deploying"}
      >
        {status === "deploying" ? "Opdaterer..." : "Opdatér fra GitHub"}
      </button>

      {status === "error" && (
        <div className="banner banner-error" style={{ marginTop: 12 }}>
          {error}
        </div>
      )}
      {status === "timeout" && (
        <div className="banner banner-error" style={{ marginTop: 12 }}>
          Kunne ikke bekræfte at opdateringen er fuldført endnu — tjek serveren manuelt (se
          DEPLOYMENT.md's fejlsøgnings-afsnit) eller genindlæs siden om lidt.
        </div>
      )}
      {status === "done" && (
        <div className="banner banner-info" style={{ marginTop: 12 }}>
          Opdateret! Kører nu build {currentBuild}.
        </div>
      )}
    </div>
  );
}

function UsersSection({ currentUserId }) {
  const [users, setUsers] = useState([]);
  const [status, setStatus] = useState("loading");
  const [updatingId, setUpdatingId] = useState(null);
  const [error, setError] = useState(null);

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
    setError(null);
    try {
      await api.updateUserRole(targetUser.id, nextRole);
      load();
    } catch (err) {
      setError(err.message);
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
      {error && <div className="banner banner-error">{error}</div>}

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
