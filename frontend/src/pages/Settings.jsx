import { useEffect, useState } from "react";
import { api } from "../api/client";
import Chip from "../components/Chip";
import "./Settings.css";

export default function Settings({ user, onSettingsChanged }) {
  const isAdmin = user.role === "admin";

  return (
    <section>
      <div className="page-header">
        <h1>Indstillinger</h1>
      </div>

      <AccountSection user={user} />
      <CardSizeSection cardSize={user.settings.card_size} onSettingsChanged={onSettingsChanged} />
      <SerialNumberSection isAdmin={isAdmin} />
      <DeletedMoviesSection />
      {isAdmin && (
        <TmdbSyncSection
          title="TMDb-synkronisering (film)"
          description="Henter frisk metadata (titel, år, poster, plot, genrer, medvirkende, rating, spilletid) fra TMDb for alle film der er oprettet via TMDb, og opdaterer det lokalt gemte. Dine egne oplysninger (tags, format, lyd-type, lokation, ejer, serienummer) rører den ikke. Kan tage et øjeblik afhængig af antal film."
          buttonLabel="Opdatér alle film fra TMDb"
          itemLabel="film"
          syncFn={api.syncMoviesFromTmdb}
        />
      )}
      {isAdmin && (
        <TmdbSyncSection
          title="TMDb-synkronisering (TV-serier)"
          description="Henter frisk metadata (navn, år, status, poster, plot, genrer, medvirkende, rating, sæson-/episodetal) fra TMDb for alle TV-serier der er oprettet via TMDb. Dine egne oplysninger (tags, format, lokation, ejer, serienummer) samt hvilke sæsoner du ejer og hvilke episoder du har set rører den ikke."
          buttonLabel="Opdatér alle TV-serier fra TMDb"
          itemLabel="TV-serier"
          syncFn={api.syncTvShowsFromTmdb}
        />
      )}
      {isAdmin && <LibraryBackupSection />}
      {isAdmin && <SystemBackupSection />}
      {isAdmin && <DatabaseResetSection />}
      {isAdmin && <SystemSettingsSection />}
      {isAdmin && <DeploySection />}
      {isAdmin && <UsersSection currentUserId={user.id} />}
      {isAdmin && <AuditLogSection />}
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

const CARD_SIZE_OPTIONS = [
  { value: "small", label: "Lille" },
  { value: "medium", label: "Mellem" },
  { value: "large", label: "Stor" },
];

function CardSizeSection({ cardSize, onSettingsChanged }) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  function selectSize(value) {
    if (value === cardSize) return;
    setSaving(true);
    setError(null);
    api
      .updateMySettings({ card_size: value })
      .then(onSettingsChanged)
      .catch((err) => setError(err.message))
      .finally(() => setSaving(false));
  }

  return (
    <div className="card settings-section">
      <h2>Kortstørrelse</h2>
      <p className="muted">
        Styrer størrelsen på film-/TV-serie-kortene i Film- og TV-serie-fanen. Én fælles
        indstilling for begge faner.
      </p>

      <div className="chip-row">
        {CARD_SIZE_OPTIONS.map((option) => (
          <Chip
            key={option.value}
            label={option.label}
            active={cardSize === option.value}
            onClick={() => selectSize(option.value)}
          />
        ))}
      </div>

      {saving && <p className="muted" style={{ marginTop: 8 }}>Gemmer...</p>}
      {error && (
        <div className="banner banner-error" style={{ marginTop: 12 }}>
          {error}
        </div>
      )}
    </div>
  );
}

function downloadJson(data, filename) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function timestampForFilename() {
  return new Date().toISOString().replace(/[:.]/g, "-");
}

function LibraryBackupSection() {
  const [exportStatus, setExportStatus] = useState("idle");
  const [exportError, setExportError] = useState(null);

  const [importFile, setImportFile] = useState(null);
  const [confirmText, setConfirmText] = useState("");
  const [importStatus, setImportStatus] = useState("idle");
  const [importError, setImportError] = useState(null);
  const [importResult, setImportResult] = useState(null);

  async function exportLibrary() {
    setExportStatus("exporting");
    setExportError(null);
    try {
      const data = await api.exportLibrary();
      downloadJson(data, `moviedb-bibliotek-${timestampForFilename()}.json`);
      setExportStatus("idle");
    } catch (err) {
      setExportError(err.message);
      setExportStatus("error");
    }
  }

  async function importLibrary() {
    if (!importFile || confirmText !== "GENDAN") return;
    setImportStatus("importing");
    setImportError(null);
    setImportResult(null);
    try {
      const text = await importFile.text();
      const data = JSON.parse(text);
      const result = await api.importLibrary(data);
      setImportResult(result);
      setImportStatus("done");
      setConfirmText("");
      setImportFile(null);
    } catch (err) {
      setImportError(err.message);
      setImportStatus("error");
    }
  }

  return (
    <div className="card settings-section">
      <h2>Bibliotek-eksport / -gendannelse</h2>
      <p className="muted">
        Eksportér hele film-/TV-biblioteket som en JSON-fil — til at bruge i et andet system, eller
        som en gendannelsesmulighed hvis biblioteket skulle blive rodet til. Dette er{" "}
        <strong>ikke</strong> en fuld system-backup (se den nedenfor) — kun selve film-/TV-dataene.
      </p>
      <button type="button" className="btn btn-primary" onClick={exportLibrary} disabled={exportStatus === "exporting"}>
        {exportStatus === "exporting" ? "Eksporterer..." : "Eksportér bibliotek"}
      </button>
      {exportStatus === "error" && (
        <div className="banner banner-error" style={{ marginTop: 12 }}>
          {exportError}
        </div>
      )}

      <hr style={{ margin: "20px 0", border: "none", borderTop: "1px solid var(--border)" }} />

      <p className="muted">
        <strong>Gendan</strong> erstatter hele det nuværende film-/TV-bibliotek med indholdet af en
        tidligere eksporteret fil — alt der ikke er i filen, forsvinder. Vælg en fil, og skriv{" "}
        <strong>GENDAN</strong> for at bekræfte.
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 10, maxWidth: 420 }}>
        <input
          type="file"
          accept="application/json"
          onChange={(e) => setImportFile(e.target.files?.[0] ?? null)}
        />
        <input
          value={confirmText}
          onChange={(e) => setConfirmText(e.target.value)}
          placeholder='Skriv "GENDAN" for at bekræfte'
        />
        <button
          type="button"
          className="btn"
          onClick={importLibrary}
          disabled={!importFile || confirmText !== "GENDAN" || importStatus === "importing"}
        >
          {importStatus === "importing" ? "Gendanner..." : "Gendan bibliotek"}
        </button>
      </div>
      {importStatus === "error" && (
        <div className="banner banner-error" style={{ marginTop: 12 }}>
          {importError}
        </div>
      )}
      {importStatus === "done" && importResult && (
        <div className="banner banner-info" style={{ marginTop: 12 }}>
          Gendannet: {importResult.movies_imported} film, {importResult.tv_shows_imported} TV-serier.
        </div>
      )}
    </div>
  );
}

function SystemBackupSection() {
  const [backupStatus, setBackupStatus] = useState("idle");
  const [backupError, setBackupError] = useState(null);

  const [restoreFile, setRestoreFile] = useState(null);
  const [confirmText, setConfirmText] = useState("");
  const [restoreStatus, setRestoreStatus] = useState("idle");
  const [restoreError, setRestoreError] = useState(null);
  const [restoreResult, setRestoreResult] = useState(null);

  async function takeBackup() {
    setBackupStatus("backing-up");
    setBackupError(null);
    try {
      const data = await api.getSystemBackup();
      downloadJson(data, `moviedb-system-backup-${timestampForFilename()}.json`);
      setBackupStatus("idle");
    } catch (err) {
      setBackupError(err.message);
      setBackupStatus("error");
    }
  }

  async function restoreBackup() {
    if (!restoreFile || confirmText !== "GENDAN SYSTEM") return;
    setRestoreStatus("restoring");
    setRestoreError(null);
    setRestoreResult(null);
    try {
      const text = await restoreFile.text();
      const data = JSON.parse(text);
      const result = await api.restoreSystemBackup(data);
      setRestoreResult(result);
      setRestoreStatus("done");
      setConfirmText("");
      setRestoreFile(null);
    } catch (err) {
      setRestoreError(err.message);
      setRestoreStatus("error");
    }
  }

  return (
    <div className="card settings-section">
      <h2>Fuld system-backup</h2>
      <p className="muted">
        Tager en fuld lavniveau-backup af hele systemet (film, TV-serier, slettede film/TV-serier,
        tags, brugere, tællere) — til katastrofe-gendannelse. <strong>Bemærk:</strong> dine eksterne
        API-nøgler (TMDb/UPC/Discogs/OMDb/Plex) er <strong>ikke</strong> med i backuppen og skal
        genindtastes manuelt under "System-indstillinger" nedenfor efter en gendannelse.
      </p>
      <button type="button" className="btn btn-primary" onClick={takeBackup} disabled={backupStatus === "backing-up"}>
        {backupStatus === "backing-up" ? "Tager backup..." : "Tag fuld system-backup"}
      </button>
      {backupStatus === "error" && (
        <div className="banner banner-error" style={{ marginTop: 12 }}>
          {backupError}
        </div>
      )}

      <hr style={{ margin: "20px 0", border: "none", borderTop: "1px solid var(--border)" }} />

      <p className="muted">
        <strong>Gendan hele systemet</strong> erstatter alt ovenstående med indholdet af en tidligere
        system-backup — inklusive brugerkonti. Vælg en fil, og skriv <strong>GENDAN SYSTEM</strong>{" "}
        for at bekræfte.
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 10, maxWidth: 420 }}>
        <input
          type="file"
          accept="application/json"
          onChange={(e) => setRestoreFile(e.target.files?.[0] ?? null)}
        />
        <input
          value={confirmText}
          onChange={(e) => setConfirmText(e.target.value)}
          placeholder='Skriv "GENDAN SYSTEM" for at bekræfte'
        />
        <button
          type="button"
          className="btn"
          onClick={restoreBackup}
          disabled={!restoreFile || confirmText !== "GENDAN SYSTEM" || restoreStatus === "restoring"}
        >
          {restoreStatus === "restoring" ? "Gendanner..." : "Gendan hele systemet"}
        </button>
      </div>
      {restoreStatus === "error" && (
        <div className="banner banner-error" style={{ marginTop: 12 }}>
          {restoreError}
        </div>
      )}
      {restoreStatus === "done" && restoreResult && (
        <div className="banner banner-info" style={{ marginTop: 12 }}>
          Gendannet: {restoreResult.movies_imported} film, {restoreResult.tv_shows_imported} TV-serier,{" "}
          {restoreResult.users_imported} brugere.
        </div>
      )}
    </div>
  );
}

function DatabaseResetSection() {
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  async function reset() {
    if (!password) return;
    setStatus("resetting");
    setError(null);
    setResult(null);
    try {
      const data = await api.resetDatabase(password);
      setResult(data);
      setStatus("done");
      setPassword("");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }

  return (
    <div className="card settings-section">
      <h2>Nulstil database</h2>
      <p className="muted">
        Tømmer film-/TV-biblioteket helt (film, TV-serier, slettede film/TV-serier, tags,
        serienummer-tællere, samt Voldby BIO-visninger/-anmodninger) tilbage til tom tilstand.{" "}
        <strong>Rører ikke</strong> brugerkonti eller system-indstillinger.{" "}
        <strong>Uigenkaldeligt</strong> — tag en fuld system-backup ovenfor først, hvis du vil kunne
        fortryde. Bekræft med din egen adgangskode.
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 10, maxWidth: 420 }}>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Din adgangskode"
          autoComplete="current-password"
        />
        <button
          type="button"
          className="btn"
          onClick={reset}
          disabled={!password || status === "resetting"}
        >
          {status === "resetting" ? "Nulstiller..." : "Nulstil database"}
        </button>
      </div>
      {status === "error" && (
        <div className="banner banner-error" style={{ marginTop: 12 }}>
          {error}
        </div>
      )}
      {status === "done" && result && (
        <div className="banner banner-info" style={{ marginTop: 12 }}>
          Nulstillet: {result.movies_removed} film, {result.tv_shows_removed} TV-serier og
          relaterede data fjernet.
        </div>
      )}
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

function TmdbSyncSection({ title, description, buttonLabel, itemLabel, syncFn }) {
  const [status, setStatus] = useState("idle");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  async function sync() {
    setStatus("syncing");
    setError(null);
    setResult(null);
    try {
      const data = await syncFn();
      setResult(data);
      setStatus("done");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }

  return (
    <div className="card settings-section">
      <h2>{title}</h2>
      <p className="muted">{description}</p>

      <button type="button" className="btn btn-primary" onClick={sync} disabled={status === "syncing"}>
        {status === "syncing" ? "Synkroniserer..." : buttonLabel}
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
                {result.synced} af {result.total} {itemLabel} opdateret, men stoppet tidligt fordi
                TMDb ramte et rate-limit. Prøv igen om lidt for at opdatere resten.
              </>
            )
          ) : (
            <>
              {result.synced} af {result.total} {itemLabel} opdateret.
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
            label="UPCDatabase-token"
            field="upcdatabase_token"
            status={statusData.upcdatabase_token}
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

const AUDIT_ACTION_LABELS = {
  "user.role_changed": "Rolle ændret",
  "system_settings.updated": "System-nøgler opdateret",
  "deploy.triggered": "OTA-opdatering udløst",
  "system_backup.created": "System-backup taget",
  "system_backup.restored": "System gendannet fra backup",
  "library_backup.exported": "Bibliotek eksporteret",
  "library_backup.imported": "Bibliotek importeret",
  "screening_request.declined": "Visningsanmodning afvist",
  "screening.scheduled": "Visning planlagt",
};

const AUDIT_PAGE_SIZE = 50;

function AuditLogSection() {
  const [entries, setEntries] = useState([]);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState("loading");

  function load(skip) {
    setStatus(skip === 0 ? "loading" : "loading-more");
    api
      .listAuditLog({ skip, limit: AUDIT_PAGE_SIZE })
      .then((data) => {
        setEntries((prev) => (skip === 0 ? data.entries : [...prev, ...data.entries]));
        setTotal(data.total);
        setStatus("ready");
      })
      .catch(() => setStatus("error"));
  }

  useEffect(() => load(0), []);

  return (
    <div className="card settings-section">
      <h2>Audit-log</h2>
      <p className="muted">
        Sikkerheds-/data-relevante handlinger (rolle-ændringer, system-nøgle-opdateringer,
        OTA-opdatering, backup/gendannelse, biograf-planlægning/afvisning), nyeste øverst.
      </p>

      {status === "loading" && <p className="muted">Indlæser...</p>}
      {status === "error" && (
        <div className="banner banner-error">Kunne ikke hente audit-log.</div>
      )}

      {entries.length > 0 && (
        <ul className="user-list">
          {entries.map((entry) => (
            <li key={entry.id} className="user-row">
              <span className="user-row-name">
                {AUDIT_ACTION_LABELS[entry.action] ?? entry.action}
                {entry.detail && <span className="muted"> — {entry.detail}</span>}
              </span>
              <span className="muted">{entry.actor}</span>
              <span className="muted">
                {new Date(entry.created_at).toLocaleString("da-DK")}
              </span>
            </li>
          ))}
        </ul>
      )}

      {status === "ready" && entries.length === 0 && (
        <p className="muted">Ingen registrerede handlinger endnu.</p>
      )}

      {entries.length < total && (
        <button
          type="button"
          className="btn"
          onClick={() => load(entries.length)}
          disabled={status === "loading-more"}
        >
          {status === "loading-more" ? "Indlæser..." : `Vis flere (${entries.length}/${total})`}
        </button>
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

  async function setStatusFor(targetUser, nextStatus) {
    setUpdatingId(targetUser.id);
    setError(null);
    try {
      await api.updateUserStatus(targetUser.id, nextStatus);
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setUpdatingId(null);
    }
  }

  const pendingCount = users.filter((u) => u.status === "pending").length;

  return (
    <div className="card settings-section">
      <h2>Brugere</h2>
      <p className="muted">
        Administrér hvem der har admin-rettigheder, og godkend/afvis nye registreringer
        {pendingCount > 0 && ` (${pendingCount} afventer godkendelse)`}.
      </p>

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
              {u.status === "pending" && <span className="role-badge">Afventer</span>}
              {u.status === "rejected" && <span className="role-badge">Afvist</span>}
              {u.status === "active" && (
                <span className="role-badge">{u.role === "admin" ? "Admin" : "Standard"}</span>
              )}
              {u.status === "pending" ? (
                <>
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={updatingId === u.id}
                    onClick={() => setStatusFor(u, "active")}
                  >
                    {updatingId === u.id ? "..." : "Godkend"}
                  </button>
                  <button
                    type="button"
                    className="btn"
                    disabled={updatingId === u.id}
                    onClick={() => setStatusFor(u, "rejected")}
                  >
                    Afvis
                  </button>
                </>
              ) : u.status === "active" ? (
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
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
