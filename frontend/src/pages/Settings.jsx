import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import Chip from "../components/Chip";
import { LANGUAGES, useLocale, useT } from "../i18n";
import "./Settings.css";

// Feature #78 — kategoriseret undermenu i stedet for én lang scroll.
// "Brugere" står bevidst først (Jans bekræftelse 2026-08-04). Et faneblad
// vises kun hvis mindst én af dets sektioner rent faktisk er synlig for den
// aktuelle rolle — de enkelte sektioners egen isAdmin/isGuest-gating
// bevares uændret nedenfor som et ekstra sikkerhedslag.
// Feature #89 — `labelKey` frem for en færdig `label`: faneblads-listen
// bygges før render, hvor oversætteren ikke er tilgængelig endnu.
function settingsTabs(isAdmin, isGuest) {
  return [
    { id: "brugere", labelKey: "settings.tab.users", visible: isAdmin },
    { id: "beskeder", labelKey: "settings.tab.messages", visible: isAdmin },
    { id: "konto", labelKey: "settings.tab.account", visible: true },
    { id: "nyt", labelKey: "settings.tab.whatsNew", visible: true },
    { id: "bibliotek", labelKey: "settings.tab.library", visible: !isGuest },
    { id: "biograf", labelKey: "settings.tab.cinema", visible: !isGuest },
    { id: "backup", labelKey: "settings.tab.backup", visible: isAdmin },
    { id: "noegler", labelKey: "settings.tab.keys", visible: isAdmin },
    { id: "drift", labelKey: "settings.tab.ops", visible: isAdmin },
  ].filter((tab) => tab.visible);
}

export default function Settings({ user, onSettingsChanged }) {
  const t = useT();
  const isAdmin = user.role === "admin";
  const isGuest = user.role === "guest";
  const tabs = settingsTabs(isAdmin, isGuest);
  const [activeTab, setActiveTab] = useState(tabs[0]?.id ?? "konto");

  return (
    <section>
      <div className="page-header">
        <h1>{t("settings.title")}</h1>
      </div>

      <div className="tabs" style={{ marginBottom: 20 }}>
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={activeTab === tab.id ? "active" : ""}
            onClick={() => setActiveTab(tab.id)}
          >
            {t(tab.labelKey)}
          </button>
        ))}
      </div>

      {activeTab === "brugere" && isAdmin && (
        <>
          <UsersSection currentUserId={user.id} />
          <AuditLogSection />
        </>
      )}

      {activeTab === "beskeder" && isAdmin && <MessagesSection currentUserId={user.id} />}

      {activeTab === "konto" && (
        <>
          <AccountSection user={user} />
          <CardSizeSection cardSize={user.settings.card_size} onSettingsChanged={onSettingsChanged} />
          <LanguageSection language={user.settings.language} onSettingsChanged={onSettingsChanged} />
          <ThemeSection theme={user.settings.theme} onSettingsChanged={onSettingsChanged} />
        </>
      )}

      {activeTab === "nyt" && <FeatureListSection />}

      {activeTab === "bibliotek" && !isGuest && (
        <>
          <SerialNumberSection isAdmin={isAdmin} />
          <DeletedMoviesSection />
          {isAdmin && (
            <TmdbSyncSection
              titleKey="sync.movieTitle"
              descriptionKey="sync.movieDescription"
              buttonLabelKey="sync.movieButton"
              itemLabelKey="sync.movieItems"
              syncFn={api.syncMoviesFromTmdb}
            />
          )}
          {isAdmin && (
            <TmdbSyncSection
              titleKey="sync.tvTitle"
              descriptionKey="sync.tvDescription"
              buttonLabelKey="sync.tvButton"
              itemLabelKey="sync.tvItems"
              syncFn={api.syncTvShowsFromTmdb}
            />
          )}
        </>
      )}

      {activeTab === "biograf" && !isGuest && <CinemaHistorySection />}

      {activeTab === "backup" && isAdmin && (
        <>
          <LibraryBackupSection />
          <SystemBackupSection />
          <DatabaseResetSection />
        </>
      )}

      {activeTab === "noegler" && isAdmin && (
        <>
          <SystemSettingsSection />
          <PlexDiagnosticsSection />
          <PlexImportSection />
        </>
      )}

      {activeTab === "drift" && isAdmin && (
        <>
          <MonitorSection />
          <DeploySection />
          <TlsCertSection />
        </>
      )}
    </section>
  );
}

function AccountSection({ user }) {
  const t = useT();
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
      <div className="modal-section-label">{t("account.heading")}</div>
      <p>
        {t("account.loggedInAs")} <strong>{user.username}</strong>{" "}
        <span className="role-badge">
          {t(
            user.role === "admin"
              ? "account.roleAdmin"
              : user.role === "guest"
                ? "account.roleGuest"
                : "account.roleStandard"
          )}
        </span>
      </p>

      <form className="serial-config-form" onSubmit={changePassword}>
        <label>
          {t("account.currentPassword")}
          <input
            type="password"
            autoComplete="current-password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            required
          />
        </label>
        <label>
          {t("account.newPassword")}
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
        {saved && <div className="banner banner-info">{t("account.passwordChanged")}</div>}

        <button type="submit" className="btn btn-primary" disabled={saving}>
          {t(saving ? "common.saving" : "account.changePassword")}
        </button>
      </form>
    </div>
  );
}

const CARD_SIZE_OPTIONS = [
  { value: "small", labelKey: "cardSize.small" },
  { value: "medium", labelKey: "cardSize.medium" },
  { value: "large", labelKey: "cardSize.large" },
];

function CardSizeSection({ cardSize, onSettingsChanged }) {
  const t = useT();
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
      <h2>{t("cardSize.heading")}</h2>
      <p className="muted">{t("cardSize.description")}</p>

      <div className="chip-row">
        {CARD_SIZE_OPTIONS.map((option) => (
          <Chip
            key={option.value}
            label={t(option.labelKey)}
            active={cardSize === option.value}
            onClick={() => selectSize(option.value)}
          />
        ))}
      </div>

      {saving && (
        <p className="muted" style={{ marginTop: 8 }}>
          {t("common.saving")}
        </p>
      )}
      {error && (
        <div className="banner banner-error" style={{ marginTop: 12 }}>
          {error}
        </div>
      )}
    </div>
  );
}

/**
 * Feature #89 — sprogvalget. Ligger under "Konto" sammen med kortstørrelse:
 * begge er personlige præferencer, ikke system-indstillinger, og gælder kun
 * den bruger der er logget ind.
 */
function LanguageSection({ language, onSettingsChanged }) {
  const t = useT();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  function selectLanguage(code) {
    if (code === language) return;
    setSaving(true);
    setError(null);
    api
      .updateMySettings({ language: code })
      .then(onSettingsChanged)
      .catch((err) => setError(err.message))
      .finally(() => setSaving(false));
  }

  return (
    <div className="card settings-section">
      <h2>{t("language.heading")}</h2>
      <p className="muted">{t("language.description")}</p>

      <div className="chip-row">
        {LANGUAGES.map((option) => (
          <Chip
            key={option.code}
            label={option.label}
            active={language === option.code}
            onClick={() => selectLanguage(option.code)}
          />
        ))}
      </div>

      {saving && <p className="muted" style={{ marginTop: 8 }}>{t("common.saving")}</p>}
      {error && (
        <div className="banner banner-error" style={{ marginTop: 12 }}>
          {t("language.saveError", { message: error })}
        </div>
      )}
    </div>
  );
}

const THEME_OPTIONS = [
  { value: "light", labelKey: "theme.light" },
  { value: "dark", labelKey: "theme.dark" },
];

/**
 * Feature #110 — tema-valget (Jans ønske 2026-08-10). Samme mønster som
 * CardSizeSection/LanguageSection lige ovenfor: en personlig præference,
 * ikke en system-indstilling. `theme` er `null` når intet er valgt endnu —
 * ingen af de to chips er så aktive, og App.jsx lader CSS'ens egen
 * `prefers-color-scheme` afgøre det i stedet (se den identiske note der).
 */
function ThemeSection({ theme, onSettingsChanged }) {
  const t = useT();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  function selectTheme(value) {
    if (value === theme) return;
    setSaving(true);
    setError(null);
    api
      .updateMySettings({ theme: value })
      .then(onSettingsChanged)
      .catch((err) => setError(err.message))
      .finally(() => setSaving(false));
  }

  return (
    <div className="card settings-section">
      <h2>{t("theme.heading")}</h2>
      <p className="muted">{t("theme.description")}</p>

      <div className="chip-row">
        {THEME_OPTIONS.map((option) => (
          <Chip
            key={option.value}
            label={t(option.labelKey)}
            /* Feature #121 — usat = mørk (ny default), så "Mørkt" markeres aktivt
               indtil brugeren evt. vælger "Lyst". */
            active={(theme || "dark") === option.value}
            onClick={() => selectTheme(option.value)}
          />
        ))}
      </div>

      {saving && <p className="muted" style={{ marginTop: 8 }}>{t("common.saving")}</p>}
      {error && (
        <div className="banner banner-error" style={{ marginTop: 12 }}>
          {t("theme.saveError", { message: error })}
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
  const t = useT();
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
      <h2>{t("libBackup.heading")}</h2>
      <p className="muted">{t("libBackup.description")}</p>
      <button type="button" className="btn btn-primary" onClick={exportLibrary} disabled={exportStatus === "exporting"}>
        {t(exportStatus === "exporting" ? "libBackup.exporting" : "libBackup.export")}
      </button>
      {exportStatus === "error" && (
        <div className="banner banner-error" style={{ marginTop: 12 }}>
          {exportError}
        </div>
      )}

      <hr style={{ margin: "20px 0", border: "none", borderTop: "1px solid var(--border)" }} />

      <p className="muted">{t("libBackup.restoreDescription")}</p>
      <div style={{ display: "flex", flexDirection: "column", gap: 10, maxWidth: 420 }}>
        <input
          type="file"
          accept="application/json"
          onChange={(e) => setImportFile(e.target.files?.[0] ?? null)}
        />
        <input
          value={confirmText}
          onChange={(e) => setConfirmText(e.target.value)}
          placeholder={t("libBackup.confirmPlaceholder")}
        />
        <button
          type="button"
          className="btn"
          onClick={importLibrary}
          disabled={!importFile || confirmText !== "GENDAN" || importStatus === "importing"}
        >
          {t(importStatus === "importing" ? "libBackup.restoring" : "libBackup.restore")}
        </button>
      </div>
      {importStatus === "error" && (
        <div className="banner banner-error" style={{ marginTop: 12 }}>
          {importError}
        </div>
      )}
      {importStatus === "done" && importResult && (
        <div className="banner banner-info" style={{ marginTop: 12 }}>
          {t("libBackup.restored", {
            movies: importResult.movies_imported,
            shows: importResult.tv_shows_imported,
          })}
        </div>
      )}
    </div>
  );
}

function SystemBackupSection() {
  const t = useT();
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
      <h2>{t("sysBackup.heading")}</h2>
      <p className="muted">{t("sysBackup.description")}</p>
      <button type="button" className="btn btn-primary" onClick={takeBackup} disabled={backupStatus === "backing-up"}>
        {t(backupStatus === "backing-up" ? "sysBackup.backingUp" : "sysBackup.take")}
      </button>
      {backupStatus === "error" && (
        <div className="banner banner-error" style={{ marginTop: 12 }}>
          {backupError}
        </div>
      )}

      <hr style={{ margin: "20px 0", border: "none", borderTop: "1px solid var(--border)" }} />

      <p className="muted">{t("sysBackup.restoreDescription")}</p>
      <div style={{ display: "flex", flexDirection: "column", gap: 10, maxWidth: 420 }}>
        <input
          type="file"
          accept="application/json"
          onChange={(e) => setRestoreFile(e.target.files?.[0] ?? null)}
        />
        <input
          value={confirmText}
          onChange={(e) => setConfirmText(e.target.value)}
          placeholder={t("sysBackup.confirmPlaceholder")}
        />
        <button
          type="button"
          className="btn"
          onClick={restoreBackup}
          disabled={!restoreFile || confirmText !== "GENDAN SYSTEM" || restoreStatus === "restoring"}
        >
          {t(restoreStatus === "restoring" ? "libBackup.restoring" : "sysBackup.restore")}
        </button>
      </div>
      {restoreStatus === "error" && (
        <div className="banner banner-error" style={{ marginTop: 12 }}>
          {restoreError}
        </div>
      )}
      {restoreStatus === "done" && restoreResult && (
        <div className="banner banner-info" style={{ marginTop: 12 }}>
          {t("sysBackup.restored", {
            movies: restoreResult.movies_imported,
            shows: restoreResult.tv_shows_imported,
            users: restoreResult.users_imported,
          })}
        </div>
      )}
    </div>
  );
}

function DatabaseResetSection() {
  const t = useT();
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
      <h2>{t("reset.heading")}</h2>
      <p className="muted">{t("reset.description")}</p>
      <div style={{ display: "flex", flexDirection: "column", gap: 10, maxWidth: 420 }}>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder={t("reset.passwordPlaceholder")}
          autoComplete="current-password"
        />
        <button
          type="button"
          className="btn"
          onClick={reset}
          disabled={!password || status === "resetting"}
        >
          {t(status === "resetting" ? "reset.resetting" : "reset.reset")}
        </button>
      </div>
      {status === "error" && (
        <div className="banner banner-error" style={{ marginTop: 12 }}>
          {error}
        </div>
      )}
      {status === "done" && result && (
        <div className="banner banner-info" style={{ marginTop: 12 }}>
          {t("reset.done", {
            movies: result.movies_removed,
            shows: result.tv_shows_removed,
          })}
        </div>
      )}
    </div>
  );
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result.split(",")[1] ?? "");
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

function formatCertDate(iso, locale) {
  return new Date(iso).toLocaleDateString(locale, { year: "numeric", month: "long", day: "numeric" });
}

function TlsCertSection() {
  const t = useT();
  const locale = useLocale();
  const [certStatus, setCertStatus] = useState(null);
  const [loadStatus, setLoadStatus] = useState("loading");

  const [csrPem, setCsrPem] = useState(null);
  const [csrStatus, setCsrStatus] = useState("idle");
  const [csrError, setCsrError] = useState(null);

  const [signedCertPem, setSignedCertPem] = useState("");
  const [completeStatus, setCompleteStatus] = useState("idle");
  const [completeError, setCompleteError] = useState(null);

  const [pkcs12File, setPkcs12File] = useState(null);
  const [pkcs12Passphrase, setPkcs12Passphrase] = useState("");
  const [pkcs12Status, setPkcs12Status] = useState("idle");
  const [pkcs12Error, setPkcs12Error] = useState(null);

  const [installPassword, setInstallPassword] = useState("");
  const [installStatus, setInstallStatus] = useState("idle");
  const [installError, setInstallError] = useState(null);

  function load() {
    setLoadStatus("loading");
    api
      .getCertStatus()
      .then((data) => {
        setCertStatus(data);
        setLoadStatus("ready");
      })
      .catch(() => setLoadStatus("error"));
  }

  useEffect(load, []);

  async function generateCsr() {
    setCsrStatus("generating");
    setCsrError(null);
    try {
      const data = await api.generateCsr();
      setCsrPem(data.csr_pem);
      setCsrStatus("ready");
      load();
    } catch (err) {
      setCsrError(err.message);
      setCsrStatus("error");
    }
  }

  async function completeCsr() {
    if (!signedCertPem.trim()) return;
    setCompleteStatus("staging");
    setCompleteError(null);
    try {
      await api.completeCsr(signedCertPem.trim());
      setCompleteStatus("done");
      setSignedCertPem("");
      load();
    } catch (err) {
      setCompleteError(err.message);
      setCompleteStatus("error");
    }
  }

  async function importPkcs12() {
    if (!pkcs12File) return;
    setPkcs12Status("importing");
    setPkcs12Error(null);
    try {
      const base64 = await fileToBase64(pkcs12File);
      await api.importPkcs12(base64, pkcs12Passphrase);
      setPkcs12Status("done");
      setPkcs12File(null);
      setPkcs12Passphrase("");
      load();
    } catch (err) {
      setPkcs12Error(err.message);
      setPkcs12Status("error");
    }
  }

  async function install() {
    if (!installPassword) return;
    setInstallStatus("installing");
    setInstallError(null);
    try {
      await api.installCert(installPassword);
      setInstallStatus("done");
      setInstallPassword("");
    } catch (err) {
      setInstallError(err.message);
      setInstallStatus("error");
    }
  }

  const expirySoon = certStatus?.days_until_expiry != null && certStatus.days_until_expiry < 30;

  return (
    <div className="card settings-section">
      <h2>{t("cert.heading")}</h2>
      <p className="muted">{t("cert.description")}</p>

      {loadStatus === "loading" && <p className="muted">{t("cert.loadingStatus")}</p>}
      {loadStatus === "error" && (
        <div className="banner banner-error">{t("cert.statusError")}</div>
      )}
      {loadStatus === "ready" && certStatus && !certStatus.installed && !certStatus.staged && (
        <p className="muted">{t("cert.none")}</p>
      )}
      {loadStatus === "ready" && certStatus && (certStatus.installed || certStatus.staged) && (
        <div className={`banner ${expirySoon ? "banner-error" : "banner-info"}`}>
          {t("cert.validity", {
            state: t(certStatus.installed ? "cert.installed" : "cert.staged"),
            name: certStatus.common_name,
            from: formatCertDate(certStatus.valid_from, locale),
            until: formatCertDate(certStatus.valid_until, locale),
            days: certStatus.days_until_expiry,
          })}
        </div>
      )}

      <hr style={{ margin: "20px 0", border: "none", borderTop: "1px solid var(--border)" }} />

      <h3 style={{ marginTop: 0 }}>{t("cert.method1")}</h3>
      <p className="muted">{t("cert.method1Description")}</p>
      <button type="button" className="btn" onClick={generateCsr} disabled={csrStatus === "generating"}>
        {t(csrStatus === "generating" ? "cert.generating" : "cert.generateCsr")}
      </button>
      {csrStatus === "error" && (
        <div className="banner banner-error" style={{ marginTop: 12 }}>{csrError}</div>
      )}
      {csrPem && (
        <div style={{ marginTop: 12 }}>
          <textarea readOnly value={csrPem} rows={8} style={{ width: "100%", fontFamily: "monospace" }} />
          <button
            type="button"
            className="btn"
            style={{ marginTop: 8 }}
            onClick={() => navigator.clipboard.writeText(csrPem).catch(() => {})}
          >
            {t("cert.copyCsr")}
          </button>
        </div>
      )}

      <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 10, maxWidth: 500 }}>
        <label className="field-label" htmlFor="signed-cert-input">
          {t("cert.pasteSignedLabel")}
        </label>
        <textarea
          id="signed-cert-input"
          value={signedCertPem}
          onChange={(e) => setSignedCertPem(e.target.value)}
          rows={8}
          style={{ width: "100%", fontFamily: "monospace" }}
          placeholder="-----BEGIN CERTIFICATE-----..."
        />
        <button
          type="button"
          className="btn"
          onClick={completeCsr}
          disabled={!signedCertPem.trim() || completeStatus === "staging"}
        >
          {t(completeStatus === "staging" ? "cert.staging" : "cert.completeCsr")}
        </button>
        {completeStatus === "error" && <div className="banner banner-error">{completeError}</div>}
        {completeStatus === "done" && (
          <div className="banner banner-info">{t("cert.readyToInstall")}</div>
        )}
      </div>

      <hr style={{ margin: "20px 0", border: "none", borderTop: "1px solid var(--border)" }} />

      <h3 style={{ marginTop: 0 }}>{t("cert.method2")}</h3>
      <p className="muted">{t("cert.method2Description")}</p>
      <div style={{ display: "flex", flexDirection: "column", gap: 10, maxWidth: 420 }}>
        <input
          type="file"
          accept=".pfx,.p12"
          onChange={(e) => setPkcs12File(e.target.files?.[0] ?? null)}
        />
        <input
          type="password"
          value={pkcs12Passphrase}
          onChange={(e) => setPkcs12Passphrase(e.target.value)}
          placeholder={t("cert.pkcs12Passphrase")}
          autoComplete="off"
        />
        <button
          type="button"
          className="btn"
          onClick={importPkcs12}
          disabled={!pkcs12File || pkcs12Status === "importing"}
        >
          {t(pkcs12Status === "importing" ? "cert.importing" : "cert.importPkcs12")}
        </button>
        {pkcs12Status === "error" && <div className="banner banner-error">{pkcs12Error}</div>}
        {pkcs12Status === "done" && (
          <div className="banner banner-info">{t("cert.readyToInstall")}</div>
        )}
      </div>

      <hr style={{ margin: "20px 0", border: "none", borderTop: "1px solid var(--border)" }} />

      <h3 style={{ marginTop: 0 }}>{t("cert.installHeading")}</h3>
      <p className="muted">{t("cert.installDescription")}</p>
      <div style={{ display: "flex", flexDirection: "column", gap: 10, maxWidth: 420 }}>
        <input
          type="password"
          value={installPassword}
          onChange={(e) => setInstallPassword(e.target.value)}
          placeholder={t("reset.passwordPlaceholder")}
          autoComplete="current-password"
        />
        <button
          type="button"
          className="btn btn-primary"
          onClick={install}
          disabled={!installPassword || !certStatus?.staged || installStatus === "installing"}
        >
          {t(installStatus === "installing" ? "cert.installing" : "cert.installNow")}
        </button>
        {installStatus === "error" && <div className="banner banner-error">{installError}</div>}
        {installStatus === "done" && (
          <div className="banner banner-info">{t("cert.installStarted")}</div>
        )}
      </div>
    </div>
  );
}

function SerialNumberSection({ isAdmin }) {
  const t = useT();
  const [status, setStatus] = useState("loading");
  const [startNumber, setStartNumber] = useState("");
  const [increment, setIncrement] = useState("");
  const [paddingWidth, setPaddingWidth] = useState("");
  // Feature #131 — genbrug af frigjorte numre (fælles til/fra) + read-only
  // oversigt over de ledige numre pr. serie.
  const [reuseFreed, setReuseFreed] = useState(false);
  const [freeNumbers, setFreeNumbers] = useState({
    physical_movies: [],
    physical_tv: [],
    digital: [],
  });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(null);

  function applyConfig(data) {
    setStartNumber(String(data.start_number));
    setIncrement(String(data.increment));
    setPaddingWidth(String(data.padding_width));
    setReuseFreed(Boolean(data.reuse_freed));
    setFreeNumbers(data.free_numbers ?? { physical_movies: [], physical_tv: [], digital: [] });
  }

  useEffect(() => {
    api
      .getSerialNumberConfig()
      .then((data) => {
        applyConfig(data);
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
        reuse_freed: reuseFreed,
      });
      applyConfig(updated);
      setSaved(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="card settings-section">
      <h2>{t("serial.heading")}</h2>
      <p className="muted">
        {t("serial.description")}
        {!isAdmin && t("serial.adminOnly")}
      </p>

      {status === "loading" && <p className="muted">{t("common.loading")}</p>}
      {status === "error" && (
        <div className="banner banner-error">{t("serial.loadError")}</div>
      )}

      {status === "ready" && (
        <form className="serial-config-form" onSubmit={save}>
          <label>
            {t("serial.nextNumber")}
            <input
              type="number"
              min="1"
              disabled={!isAdmin}
              value={startNumber}
              onChange={(e) => setStartNumber(e.target.value)}
            />
          </label>
          <label>
            {t("serial.increment")}
            <input
              type="number"
              min="1"
              disabled={!isAdmin}
              value={increment}
              onChange={(e) => setIncrement(e.target.value)}
            />
          </label>
          <label>
            {t("serial.padding")}
            <input
              type="number"
              min="0"
              max="10"
              disabled={!isAdmin}
              value={paddingWidth}
              onChange={(e) => setPaddingWidth(e.target.value)}
            />
          </label>

          {/* Feature #131 — til/fra for genbrug af frigjorte numre. */}
          <label className="serial-reuse-toggle">
            <input
              type="checkbox"
              disabled={!isAdmin}
              checked={reuseFreed}
              onChange={(e) => setReuseFreed(e.target.checked)}
            />
            {t("serial.reuseFreed")}
          </label>
          <p className="muted serial-reuse-hint">{t("serial.reuseFreedHint")}</p>

          <div className="serial-free-numbers">
            <div className="modal-section-label">{t("serial.freeNumbers")}</div>
            <SerialFreeList label={t("serial.freeMovies")} numbers={freeNumbers.physical_movies} prefix="M" t={t} />
            <SerialFreeList label={t("serial.freeTv")} numbers={freeNumbers.physical_tv} prefix="T" t={t} />
            <SerialFreeList label={t("serial.freeDigital")} numbers={freeNumbers.digital} prefix="D" t={t} />
          </div>

          {error && <div className="banner banner-error">{error}</div>}
          {saved && <div className="banner banner-info">{t("serial.saved")}</div>}

          {isAdmin && (
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {t(saving ? "common.saving" : "common.save")}
            </button>
          )}
        </form>
      )}
    </div>
  );
}

// Feature #131 — én række "ledige numre" for en serie (M/T/D). Tom serie viser
// en dæmpet "ingen"-tekst frem for en tom liste.
function SerialFreeList({ label, numbers, prefix, t }) {
  return (
    <div className="serial-free-row">
      <span className="serial-free-label">{label}</span>
      <span className="serial-free-values">
        {numbers.length > 0
          ? numbers.map((n) => `${prefix}#${n}`).join(", ")
          : t("serial.freeNone")}
      </span>
    </div>
  );
}

// Feature #115 — Nyheder-fanen: viser oversigts-tabellen fra FEATURES.md
// (hentet server-side), så portalens brugere kan se hvad der bliver lavet
// uden adgang til det private GitHub-repo. Synlig for alle roller.
const FEATURE_STATUS_META = {
  done: { labelKey: "features.status.done", className: "feature-status--done" },
  "in-progress": { labelKey: "features.status.inProgress", className: "feature-status--progress" },
  planned: { labelKey: "features.status.planned", className: "feature-status--planned" },
  droppet: { labelKey: "features.status.dropped", className: "feature-status--dropped" },
};

function FeatureListSection() {
  const t = useT();
  const [items, setItems] = useState([]);
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    api
      .getFeatureList()
      .then((data) => {
        setItems(data);
        setStatus("ready");
      })
      .catch(() => setStatus("error"));
  }, []);

  return (
    <div className="card settings-section">
      <h2>{t("features.heading")}</h2>
      <p className="muted">{t("features.description")}</p>

      {status === "loading" && <p className="muted">{t("common.loading")}</p>}
      {status === "error" && (
        <div className="banner banner-error">{t("features.loadError")}</div>
      )}

      {status === "ready" && items.length === 0 && (
        <p className="muted">{t("features.none")}</p>
      )}

      {status === "ready" && items.length > 0 && (
        <ul className="feature-list">
          {items.map((item) => {
            // Ukendt status vises råt frem for at forsvinde (fejlsikkert).
            const meta = FEATURE_STATUS_META[item.status];
            return (
              <li key={item.number} className="feature-row">
                <span className="feature-name">{item.name}</span>
                <span className={`feature-status ${meta?.className ?? ""}`}>
                  {meta ? t(meta.labelKey) : item.status}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

const DELETED_MOVIES_PAGE_SIZE = 10;

function DeletedMoviesSection() {
  const t = useT();
  const locale = useLocale();
  const [entries, setEntries] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [status, setStatus] = useState("loading");

  function load(pageIndex) {
    setStatus("loading");
    api
      .listDeletedMovies({ skip: pageIndex * DELETED_MOVIES_PAGE_SIZE, limit: DELETED_MOVIES_PAGE_SIZE })
      .then((data) => {
        setEntries(data.entries);
        setTotal(data.total);
        setPage(pageIndex);
        setStatus("ready");
      })
      .catch(() => setStatus("error"));
  }

  useEffect(() => load(0), []);

  const totalPages = Math.max(1, Math.ceil(total / DELETED_MOVIES_PAGE_SIZE));

  return (
    <div className="card settings-section">
      <h2>{t("deleted.heading")}</h2>
      <p className="muted">{t("deleted.description")}</p>

      {status === "loading" && <p className="muted">{t("common.loading")}</p>}
      {status === "error" && (
        <div className="banner banner-error">{t("deleted.loadError")}</div>
      )}

      {status === "ready" && entries.length === 0 && (
        <p className="muted">{t("deleted.none")}</p>
      )}

      {entries.length > 0 && (
        <ul className="user-list">
          {entries.map((entry) => (
            <li key={entry.id} className="user-row">
              <span className="user-row-name">
                #{entry.serial_number ?? "—"} · {entry.title}
                {entry.year ? ` (${entry.year})` : ""}
              </span>
              <span className="muted">
                {t("deleted.by", {
                  who: entry.deleted_by ?? t("deleted.unknownUser"),
                  date: new Date(entry.deleted_at).toLocaleDateString(locale),
                })}
              </span>
            </li>
          ))}
        </ul>
      )}

      {total > DELETED_MOVIES_PAGE_SIZE && (
        <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 12 }}>
          <button
            type="button"
            className="btn"
            onClick={() => load(page - 1)}
            disabled={page === 0 || status === "loading"}
          >
            {t("audit.previous")}
          </button>
          <span className="muted">{t("audit.page", { page: page + 1, totalPages })}</span>
          <button
            type="button"
            className="btn"
            onClick={() => load(page + 1)}
            disabled={page + 1 >= totalPages || status === "loading"}
          >
            {t("audit.next")}
          </button>
        </div>
      )}
    </div>
  );
}

// Feature #130 — historik over afholdte biograf-fremvisninger (Jans ønske
// 2026-08-12), nyeste øverst. Kun læsning; selve planlægningen sker fortsat på
// Voldby BIO-fanen. Data kommer fra `GET /api/screenings?past=true`.
function CinemaHistorySection() {
  const t = useT();
  const locale = useLocale();
  const [entries, setEntries] = useState([]);
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    api
      .listScreeningHistory()
      .then((data) => {
        setEntries(data);
        setStatus("ready");
      })
      .catch(() => setStatus("error"));
  }, []);

  return (
    <div className="card settings-section">
      <h2>{t("cinemaHistory.heading")}</h2>
      <p className="muted">{t("cinemaHistory.description")}</p>

      {status === "loading" && <p className="muted">{t("common.loading")}</p>}
      {status === "error" && (
        <div className="banner banner-error">{t("cinemaHistory.loadError")}</div>
      )}

      {status === "ready" && entries.length === 0 && (
        <p className="muted">{t("cinemaHistory.none")}</p>
      )}

      {status === "ready" && entries.length > 0 && (
        <ul className="user-list">
          {entries.map((s) => (
            <li key={s.id} className="user-row">
              <span className="user-row-name">
                {s.title ?? t("cinemaHistory.unknownTitle")}
                {s.year ? ` (${s.year})` : ""}
                {s.note ? ` — ${s.note}` : ""}
              </span>
              <span className="muted">
                {new Date(s.scheduled_at).toLocaleString(locale, {
                  dateStyle: "medium",
                  timeStyle: "short",
                })}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function TmdbSyncSection({ titleKey, descriptionKey, buttonLabelKey, itemLabelKey, syncFn }) {
  const t = useT();
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
      <h2>{t(titleKey)}</h2>
      <p className="muted">{t(descriptionKey)}</p>

      <button type="button" className="btn btn-primary" onClick={sync} disabled={status === "syncing"}>
        {status === "syncing" ? t("sync.syncing") : t(buttonLabelKey)}
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
              t("sync.abortedNoToken")
            ) : (
              t("sync.rateLimited", {
                synced: result.synced,
                total: result.total,
                items: t(itemLabelKey),
              })
            )
          ) : (
            <>
              {t("sync.done", {
                synced: result.synced,
                total: result.total,
                items: t(itemLabelKey),
              })}
              {result.failed > 0 &&
                t("sync.failedSuffix", {
                  failed: result.failed,
                  titles: result.failed_titles.join(", "),
                })}
            </>
          )}
        </div>
      )}
    </div>
  );
}

function SystemSettingsSection() {
  const t = useT();
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
      <h2>{t("sys.heading")}</h2>
      <p className="muted">{t("sys.description")}</p>

      {loadStatus === "loading" && <p className="muted">{t("common.loading")}</p>}
      {loadStatus === "error" && (
        <div className="banner banner-error">{t("sys.statusError")}</div>
      )}

      {loadStatus === "ready" && statusData && (
        <>
          <PrimaryBarcodeSourceRow
            currentValue={statusData.primary_barcode_source}
            onSaved={load}
          />
          <ApiKeyRow
            label="TMDb API-token"
            field="tmdb_api_token"
            status={statusData.tmdb_api_token}
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
            label="EAN-Search.org-token"
            field="ean_search_api_key"
            status={statusData.ean_search_api_key}
            onSaved={load}
          />
          <ApiKeyRow
            label={t("sys.omdbKey")}
            field="omdb_api_key"
            status={statusData.omdb_api_key}
            onSaved={load}
          />
          <PlainSettingRow
            label={t("sys.plexServerUrl")}
            field="plex_server_url"
            hint={t("sys.plexServerUrlHint")}
            currentValue={statusData.plex_server_url}
            onSaved={load}
          />
          <ApiKeyRow
            label={t("sys.plexToken")}
            field="plex_token"
            status={statusData.plex_token}
            onSaved={load}
            testable={false}
          />
        </>
      )}
    </div>
  );
}

/**
 * Feature #88 — fejlsøgning af den automatiske Plex-kontrol.
 *
 * Uden den er "hvorfor har mine film ikke Plex-badges?" et sort hul: det kan
 * være forbindelsen, token'et, en sektion der ikke blev fundet, en Plex-agent
 * uden TMDb-id'er, eller titler der bare ikke matcher. Panelet skiller de
 * fem ad, og viser konkret hvilke af *dine* film der ikke kunne matches.
 */
function PlexDiagnosticsSection() {
  const t = useT();
  const [status, setStatus] = useState("idle"); // idle | running | done | error
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  function run() {
    setStatus("running");
    setError(null);
    api
      .getPlexDiagnostics()
      .then((result) => {
        setData(result);
        setStatus("done");
      })
      .catch((err) => {
        setError(err.message);
        setStatus("error");
      });
  }

  const noTmdbGuids =
    data?.ok && data.sections.length > 0 && data.sections.every((s) => s.with_tmdb_guid === 0);

  return (
    <div className="card settings-section">
      <h2>{t("plexDiag.heading")}</h2>
      <p className="muted">{t("plexDiag.description")}</p>

      <button type="button" className="btn btn-primary" onClick={run} disabled={status === "running"}>
        {t(status === "running" ? "plexDiag.testing" : "plexDiag.test")}
      </button>

      {status === "error" && <div className="banner banner-error">{error}</div>}

      {status === "done" && data && (
        <div className="plex-diagnostics">
          {data.ok ? (
            <div className="banner banner-info">
              {t("plexDiag.connected", {
                server: data.server_name ?? "Plex",
                version: data.server_version ?? "?",
                ms: data.duration_ms,
              })}
            </div>
          ) : (
            <div className="banner banner-error">{data.error}</div>
          )}

          <dl className="plex-diag-grid">
            <div>
              <dt>{t("plexDiag.serverUrl")}</dt>
              <dd>{data.server_url || <span className="muted">{t("plexDiag.notSet")}</span>}</dd>
            </div>
            <div>
              <dt>{t("plexDiag.token")}</dt>
              <dd>
                {data.token_configured ? (
                  t("plexDiag.tokenSet")
                ) : (
                  <span className="muted">{t("plexDiag.notSet")}</span>
                )}
              </dd>
            </div>
            {data.ok && (
              <>
                <div>
                  <dt>{t("plexDiag.moviesInPlex")}</dt>
                  <dd>{data.plex_movie_count}</dd>
                </div>
                <div>
                  <dt>{t("plexDiag.showsInPlex")}</dt>
                  <dd>{data.plex_show_count}</dd>
                </div>
                <div>
                  <dt>{t("plexDiag.moviesMatched")}</dt>
                  <dd>
                    {t("plexDiag.ofTotal", {
                      matched: data.matched_movies,
                      total: data.library_movie_count,
                    })}
                  </dd>
                </div>
                <div>
                  <dt>{t("plexDiag.showsMatched")}</dt>
                  <dd>
                    {t("plexDiag.ofTotal", {
                      matched: data.matched_shows,
                      total: data.library_show_count,
                    })}
                  </dd>
                </div>
                <div>
                  <dt>{t("plexDiag.matchedByTmdb")}</dt>
                  <dd>{data.matched_by_tmdb}</dd>
                </div>
                <div>
                  <dt>{t("plexDiag.matchedByTitle")}</dt>
                  <dd>{data.matched_by_title}</dd>
                </div>
              </>
            )}
          </dl>

          {data.ok && data.sections.length === 0 && (
            <div className="banner banner-error">{t("plexDiag.noSections")}</div>
          )}

          {noTmdbGuids && (
            <div className="banner banner-info">{t("plexDiag.noTmdbGuids")}</div>
          )}

          {data.sections.length > 0 && (
            <>
              <h3>{t("plexDiag.librariesHeading")}</h3>
              <table className="plex-diag-table">
                <thead>
                  <tr>
                    <th>{t("plexDiag.colLibrary")}</th>
                    <th>{t("plexDiag.colType")}</th>
                    <th>{t("plexDiag.colItems")}</th>
                    <th>{t("plexDiag.colTmdb")}</th>
                    <th>{t("plexDiag.colImdb")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.sections.map((section) => (
                    <tr key={section.key}>
                      <td>{section.title}</td>
                      <td>{t(section.type === "movie" ? "app.nav.movies" : "app.nav.tv")}</td>
                      <td>{section.item_count}</td>
                      <td>{section.with_tmdb_guid}</td>
                      <td>{section.with_imdb_guid}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}

          {data.ok && (data.unmatched_movies.length > 0 || data.unmatched_shows.length > 0) && (
            <>
              <h3>{t("plexDiag.unmatchedHeading")}</h3>
              <p className="muted">{t("plexDiag.unmatchedHint")}</p>
              <ul className="plex-diag-unmatched">
                {[...data.unmatched_movies, ...data.unmatched_shows].map((item, i) => (
                  <li key={`${item.title}-${i}`}>
                    {item.title}
                    {item.year ? ` (${item.year})` : ""}
                    {item.tmdb_id ? ` — TMDb ${item.tmdb_id}` : t("plexDiag.noTmdbId")}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </div>
  );
}

// Backendens handlings-koder mappet til oversættelsesnøgler. En ukendt kode
// (fx en nyere backend mod en ældre frontend) falder tilbage til koden selv.
/**
 * Feature #90 — importér det Plex allerede har.
 *
 * Altid forhåndsvisning før udførelse: en import kan oprette hundredvis af
 * poster, og der er ingen fortryd-knap bagefter ud over at slette dem igen.
 * Begge trin rammer samme endpoint med forskellig `dry_run`, så det viste og
 * det udførte ikke kan drive fra hinanden.
 */
function PlexImportSection() {
  const t = useT();
  const [includeMovies, setIncludeMovies] = useState(true);
  const [includeShows, setIncludeShows] = useState(true);
  const [tag, setTag] = useState("Plex-import");
  const [status, setStatus] = useState("idle"); // idle | previewing | preview | importing | done | error
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  function call(dryRun) {
    setStatus(dryRun ? "previewing" : "importing");
    setError(null);
    api
      .importFromPlex({
        dry_run: dryRun,
        include_movies: includeMovies,
        include_shows: includeShows,
        tag,
      })
      .then((result) => {
        setData(result);
        // Backend svarer 200 med ok:false ved manglende konfiguration — det
        // er ikke en netværksfejl, men skal stadig vises som en fejl her.
        if (!result.ok) {
          setError(result.error);
          setStatus("error");
          return;
        }
        setStatus(dryRun ? "preview" : "done");
      })
      .catch((err) => {
        setError(err.message);
        setStatus("error");
      });
  }

  const busy = status === "previewing" || status === "importing";

  return (
    <div className="card settings-section">
      <h2>{t("plexImport.heading")}</h2>
      <p className="muted">{t("plexImport.description")}</p>

      <div className="chip-row" style={{ marginBottom: 12 }}>
        <Chip
          label={t("plexImport.includeMovies")}
          active={includeMovies}
          onClick={() => setIncludeMovies((v) => !v)}
        />
        <Chip
          label={t("plexImport.includeShows")}
          active={includeShows}
          onClick={() => setIncludeShows((v) => !v)}
        />
      </div>

      <div className="serial-config-form" style={{ marginBottom: 12 }}>
        <label>
          {t("plexImport.tagLabel")} — <span className="muted">{t("plexImport.tagHint")}</span>
          <input value={tag} onChange={(e) => setTag(e.target.value)} maxLength={60} />
        </label>
      </div>

      <button
        type="button"
        className="btn"
        onClick={() => call(true)}
        disabled={busy || (!includeMovies && !includeShows)}
      >
        {t(status === "previewing" ? "plexImport.previewing" : "plexImport.preview")}
      </button>

      {status === "error" && (
        <div className="banner banner-error" style={{ marginTop: 12 }}>
          {error}
        </div>
      )}

      {/* "importing" er med her: uden den forsvandt hele blokken mens
          importen kørte, så man stod uden feedback under et kald der kan
          tage minutter for et stort bibliotek. */}
      {(status === "preview" || status === "importing" || status === "done") && data && (
        <div className="plex-diagnostics">
          {data.imported.length === 0 && data.unmatched.length === 0 ? (
            <div className="banner banner-info">{t("plexImport.nothingToImport")}</div>
          ) : (
            <div className="banner banner-info">
              {t(status === "preview" ? "plexImport.previewSummary" : "plexImport.doneSummary", {
                count: data.imported.length,
                present: data.already_present,
              })}
            </div>
          )}

          {data.stopped_early && (
            <div className="banner banner-error">{t("plexImport.rateLimited")}</div>
          )}

          {(status === "preview" || status === "importing") && data.imported.length > 0 && (
            <>
              <p className="muted" style={{ margin: 0 }}>
                {t("plexImport.confirmHint")}
              </p>
              <div style={{ display: "flex", gap: 8 }}>
                <button type="button" className="btn btn-primary" onClick={() => call(false)} disabled={busy}>
                  {t(status === "importing" ? "plexImport.running" : "plexImport.run", {
                    count: data.imported.length,
                  })}
                </button>
                <button type="button" className="btn" onClick={() => setStatus("idle")} disabled={busy}>
                  {t("plexImport.cancel")}
                </button>
              </div>
            </>
          )}

          {data.imported.length > 0 && (
            <ul className="plex-diag-unmatched">
              {data.imported.map((item) => (
                <li key={`${item.kind}-${item.tmdb_id}`}>
                  {item.title}
                  {item.year ? ` (${item.year})` : ""}
                  {/* Feature #91 — formatet kendes for film allerede i
                      forhåndsvisningen; for serier ligger opløsningen på
                      episoderne og afgøres først ved selve importen. */}
                  {item.format && <span className="muted"> — {item.format}</span>}
                  {item.format_is_fallback && (
                    <span className="muted"> ({t("plexImport.formatFallback")})</span>
                  )}
                  {item.resolved_via === "tmdb_search" && (
                    <span className="muted"> — {t("plexImport.viaSearch")}</span>
                  )}
                </li>
              ))}
            </ul>
          )}

          {data.unmatched.length > 0 && (
            <>
              <h3>{t("plexImport.unmatchedHeading", { count: data.unmatched.length })}</h3>
              <p className="muted">{t("plexImport.unmatchedHint")}</p>
              <ul className="plex-diag-unmatched">
                {data.unmatched.map((item, i) => (
                  <li key={`${item.title}-${i}`}>
                    {item.title}
                    {item.year ? ` (${item.year})` : ""}
                  </li>
                ))}
              </ul>
            </>
          )}

          {data.failed.length > 0 && (
            <>
              <h3>{t("plexImport.failedHeading", { count: data.failed.length })}</h3>
              <p className="muted">{t("plexImport.failedHint")}</p>
              <ul className="plex-diag-unmatched">
                {data.failed.map((item, i) => (
                  <li key={`${item.title}-${i}`}>
                    {item.title}
                    {item.reason ? <span className="muted"> — {item.reason}</span> : null}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Feature #100 — admin sender beskeder til alle eller til én bruger, og ser
 * hvem der har læst dem.
 *
 * Modtagerlisten er et øjebliksbillede taget ved afsendelse (Jans valg), så
 * en besked om fredagens visning ikke møder en bruger der opretter sig tre
 * måneder senere. Det er også derfor "læst af 2 af 5" er et fast tal og
 * ikke ændrer sig når der kommer nye brugere til.
 */
function MessagesSection({ currentUserId }) {
  const t = useT();
  const locale = useLocale();
  const [users, setUsers] = useState([]);
  const [messages, setMessages] = useState([]);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [recipient, setRecipient] = useState("");
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState(null);

  function load() {
    api.listMessages().then(setMessages).catch((err) => setError(err.message));
    api.listUsers().then(setUsers).catch(() => {});
  }

  useEffect(load, []);

  async function send(event) {
    event.preventDefault();
    setStatus("sending");
    setError(null);
    try {
      await api.sendMessage({
        subject,
        body,
        recipient_user_id: recipient || null,
      });
      setSubject("");
      setBody("");
      setRecipient("");
      setStatus("idle");
      load();
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }

  async function remove(messageId) {
    if (!window.confirm(t("messages.confirmDelete"))) return;
    try {
      await api.deleteMessage(messageId);
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  // Kun aktive brugere kan modtage, og man sender ikke til sig selv — samme
  // regel som backenden håndhæver, gentaget her så listen ikke tilbyder valg
  // der ville blive afvist.
  const selectableUsers = users.filter(
    (u) => u.status === "active" && u.id !== currentUserId
  );

  return (
    <div className="card settings-section">
      <h2>{t("messages.heading")}</h2>
      <p className="muted">{t("messages.description")}</p>

      <form className="serial-config-form" onSubmit={send} style={{ maxWidth: 520 }}>
        <label>
          {t("messages.recipient")}
          <select value={recipient} onChange={(e) => setRecipient(e.target.value)}>
            <option value="">{t("messages.everyone")}</option>
            {selectableUsers.map((u) => (
              <option key={u.id} value={u.id}>
                {u.username}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t("messages.subject")}
          <input
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            maxLength={120}
            required
          />
        </label>
        <label>
          {t("messages.body")}
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={4}
            maxLength={2000}
            required
            style={{ resize: "vertical" }}
          />
        </label>

        {error && <div className="banner banner-error">{error}</div>}

        <button
          type="submit"
          className="btn btn-primary"
          disabled={status === "sending" || !subject.trim() || !body.trim()}
        >
          {t(status === "sending" ? "messages.sending" : "messages.send")}
        </button>
      </form>

      <hr style={{ margin: "20px 0", border: "none", borderTop: "1px solid var(--border)" }} />

      <h3 style={{ marginTop: 0 }}>{t("messages.sentHeading")}</h3>
      {messages.length === 0 ? (
        <p className="muted">{t("messages.noneSent")}</p>
      ) : (
        <ul className="user-list">
          {messages.map((message) => (
            <li key={message.id} className="message-sent-row">
              <div className="message-sent-main">
                <strong>{message.subject}</strong>
                <div className="muted message-sent-meta">
                  {t(message.is_broadcast ? "messages.toEveryone" : "messages.toOne", {
                    name: message.recipients[0]?.username ?? "",
                    date: new Date(message.created_at).toLocaleDateString(locale),
                  })}
                  {" · "}
                  {t("messages.readCount", {
                    read: message.read_count,
                    total: message.recipient_count,
                  })}
                </div>
                {/* Kun de der faktisk har læst listes: "hvem mangler" er
                    hurtigere at aflæse ud fra tallet end ud fra to lister. */}
                {message.read_count > 0 && (
                  <div className="muted message-sent-meta">
                    {t("messages.readBy", {
                      names: message.recipients
                        .filter((r) => r.read_at)
                        .map((r) => r.username)
                        .join(", "),
                    })}
                  </div>
                )}
              </div>
              <button type="button" className="btn" onClick={() => remove(message.id)}>
                {t("common.delete")}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

const AUDIT_ACTION_KEYS = {
  "user.role_changed": "audit.action.roleChanged",
  "system_settings.updated": "audit.action.settingsUpdated",
  "deploy.triggered": "audit.action.deployTriggered",
  "system_backup.created": "audit.action.backupCreated",
  "system_backup.restored": "audit.action.backupRestored",
  "library_backup.exported": "audit.action.libraryExported",
  "library_backup.imported": "audit.action.libraryImported",
  "screening_request.declined": "audit.action.requestDeclined",
  "screening.scheduled": "audit.action.screeningScheduled",
  "message.sent": "audit.action.messageSent",
  "plex.imported": "audit.action.plexImported",
  "system.service_restarted": "audit.action.serviceRestarted",
  "system.reboot_triggered": "audit.action.rebootTriggered",
};

const AUDIT_PAGE_SIZE = 10;

function AuditLogSection() {
  const t = useT();
  const locale = useLocale();
  const [entries, setEntries] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [status, setStatus] = useState("loading");

  function load(pageIndex) {
    setStatus("loading");
    api
      .listAuditLog({ skip: pageIndex * AUDIT_PAGE_SIZE, limit: AUDIT_PAGE_SIZE })
      .then((data) => {
        setEntries(data.entries);
        setTotal(data.total);
        setPage(pageIndex);
        setStatus("ready");
      })
      .catch(() => setStatus("error"));
  }

  useEffect(() => load(0), []);

  const totalPages = Math.max(1, Math.ceil(total / AUDIT_PAGE_SIZE));

  return (
    <div className="card settings-section">
      <h2>{t("audit.heading")}</h2>
      <p className="muted">{t("audit.description")}</p>

      {status === "loading" && <p className="muted">{t("common.loading")}</p>}
      {status === "error" && (
        <div className="banner banner-error">{t("audit.loadError")}</div>
      )}

      {entries.length > 0 && (
        <ul className="user-list">
          {entries.map((entry) => (
            <li key={entry.id} className="user-row">
              <span className="user-row-name">
                {AUDIT_ACTION_KEYS[entry.action] ? t(AUDIT_ACTION_KEYS[entry.action]) : entry.action}
                {entry.detail && <span className="muted"> — {entry.detail}</span>}
              </span>
              <span className="muted">{entry.actor}</span>
              <span className="muted">
                {new Date(entry.created_at).toLocaleDateString(locale)}{" "}
                {new Date(entry.created_at).toLocaleTimeString(locale)}
              </span>
            </li>
          ))}
        </ul>
      )}

      {status === "ready" && entries.length === 0 && (
        <p className="muted">{t("audit.empty")}</p>
      )}

      {total > AUDIT_PAGE_SIZE && (
        <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 12 }}>
          <button
            type="button"
            className="btn"
            onClick={() => load(page - 1)}
            disabled={page === 0 || status === "loading"}
          >
            {t("audit.previous")}
          </button>
          <span className="muted">
            {t("audit.page", { page: page + 1, totalPages })}
          </span>
          <button
            type="button"
            className="btn"
            onClick={() => load(page + 1)}
            disabled={page + 1 >= totalPages || status === "loading"}
          >
            {t("audit.next")}
          </button>
        </div>
      )}
    </div>
  );
}

const BARCODE_SOURCE_LABELS = {
  upcitemdb: "UPCitemdb",
  discogs: "Discogs",
  upcdatabase: "UPCDatabase.org",
  ean_search: "EAN-Search.org",
};

function PrimaryBarcodeSourceRow({ currentValue, onSaved }) {
  const t = useT();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  async function handleChange(event) {
    const value = event.target.value;
    setSaving(true);
    setError(null);
    try {
      await api.updateSystemSettings({ primary_barcode_source: value });
      onSaved();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="serial-config-form" style={{ marginBottom: 16 }}>
      <label>
        {t("sys.primarySource")}{" "}
        <span className="muted">{t("sys.primarySourceHint")}</span>
        <select value={currentValue ?? "upcitemdb"} onChange={handleChange} disabled={saving}>
          {Object.entries(BARCODE_SOURCE_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </label>
      {error && <div className="banner banner-error">{error}</div>}
    </div>
  );
}

function PlainSettingRow({ label, field, hint, currentValue, onSaved }) {
  const t = useT();
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
      {saved && <div className="banner banner-info">{t("serial.saved")}</div>}

      <button type="submit" className="btn btn-primary" disabled={saving}>
        {t(saving ? "common.saving" : "common.save")}
      </button>
    </form>
  );
}

function ApiKeyRow({ label, field, status, onSaved, testable = true }) {
  const t = useT();
  const [value, setValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(null);
  const [testStatus, setTestStatus] = useState("idle");
  const [testResult, setTestResult] = useState(null);

  async function submit(newValue) {
    setSaving(true);
    setError(null);
    setSaved(false);
    setTestResult(null);
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

  async function testConnection() {
    setTestStatus("testing");
    setTestResult(null);
    try {
      const result = await api.testSystemSetting(field);
      setTestResult(result);
    } catch (err) {
      setTestResult({ ok: false, message: err.message });
    } finally {
      setTestStatus("idle");
    }
  }

  const sourceLabel = t(
    status.source === "custom"
      ? "sys.sourceCustom"
      : status.source === "env"
        ? "sys.sourceEnv"
        : "sys.sourceUnset"
  );

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
            placeholder={t(
            status.configured ? "sys.keyPlaceholderSet" : "sys.keyPlaceholderUnset"
          )}
          value={value}
          onChange={(e) => setValue(e.target.value)}
        />
      </label>

      {error && <div className="banner banner-error">{error}</div>}
      {saved && <div className="banner banner-info">{t("serial.saved")}</div>}
      {testResult && (
        <div className={`banner ${testResult.ok ? "banner-info" : "banner-error"}`}>
          {testResult.ok ? "✓" : "✗"} {testResult.message}
        </div>
      )}

      <div style={{ display: "flex", gap: 8 }}>
        <button type="submit" className="btn btn-primary" disabled={saving || !value}>
          {t(saving ? "common.saving" : "common.save")}
        </button>
        {status.source === "custom" && (
          <button type="button" className="btn" onClick={() => submit("")} disabled={saving}>
            {t("sys.clearUseEnv")}
          </button>
        )}
        {testable && (
          <button
            type="button"
            className="btn"
            onClick={testConnection}
            disabled={testStatus === "testing" || !status.configured}
          >
            {t(testStatus === "testing" ? "sys.testing" : "sys.testConnection")}
          </button>
        )}
      </div>
    </form>
  );
}

// Feature #154 — CPU/RAM/disk/tjeneste-status + genstart, under Drift-fanen.
export function formatUptime(seconds) {
  if (seconds == null) return "—";
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (days > 0) return `${days}d ${hours}t`;
  if (hours > 0) return `${hours}t ${minutes}m`;
  return `${minutes}m`;
}

function MonitorMetric({ label, percent, detail }) {
  const value = percent ?? 0;
  return (
    <div className="monitor-metric">
      <div className="monitor-metric-label">
        <span>{label}</span>
        <span>{percent != null ? `${percent}%` : "—"}</span>
      </div>
      <div className="monitor-metric-bar">
        <div className="monitor-metric-bar-fill" style={{ width: `${Math.min(value, 100)}%` }} />
      </div>
      {detail && <div className="monitor-metric-detail muted">{detail}</div>}
    </div>
  );
}

function MonitorSection() {
  const t = useT();
  const [health, setHealth] = useState(null);
  const [healthError, setHealthError] = useState(null);

  const [restartStatus, setRestartStatus] = useState("idle");
  const [restartError, setRestartError] = useState(null);

  const [rebootPassword, setRebootPassword] = useState("");
  const [rebootStatus, setRebootStatus] = useState("idle");
  const [rebootError, setRebootError] = useState(null);

  async function loadHealth(background) {
    try {
      const data = await api.getSystemHealth(background);
      setHealth(data);
      setHealthError(null);
    } catch (err) {
      if (!background) setHealthError(err.message);
    }
  }

  useEffect(() => {
    loadHealth(false);
    const interval = setInterval(() => loadHealth(true), 10_000);
    return () => clearInterval(interval);
  }, []);

  // Poller /api/health (ubeskyttet, kræver ikke login) indtil backend'en
  // svarer igen, eller tiden løber ud — samme grundmønster som
  // DeploySection's polling nedenfor, men uden build-nummer-sammenligningen
  // (en genstart ændrer ikke build-nummeret, kun om processen kører).
  function waitForHealthAgain(maxMs, intervalMs, onSuccess, onTimeout) {
    const deadline = Date.now() + maxMs;
    const poll = setInterval(async () => {
      if (Date.now() > deadline) {
        clearInterval(poll);
        onTimeout();
        return;
      }
      try {
        await api.health();
        clearInterval(poll);
        onSuccess();
      } catch {
        // Stadig nede (eller midt i en genstart) — prøv igen ved næste tick.
      }
    }, intervalMs);
  }

  async function restartService() {
    setRestartStatus("restarting");
    setRestartError(null);
    try {
      await api.restartService();
    } catch (err) {
      setRestartError(err.message);
      setRestartStatus("error");
      return;
    }
    waitForHealthAgain(
      30_000,
      2000,
      () => {
        setRestartStatus("done");
        loadHealth(true);
      },
      () => setRestartStatus("done")
    );
  }

  async function rebootServer() {
    if (!rebootPassword) return;
    setRebootStatus("rebooting");
    setRebootError(null);
    try {
      await api.rebootServer(rebootPassword);
      setRebootPassword("");
    } catch (err) {
      setRebootError(err.message);
      setRebootStatus("error");
      return;
    }
    waitForHealthAgain(
      180_000,
      5000,
      () => {
        setRebootStatus("done");
        loadHealth(true);
      },
      () => setRebootStatus("timeout")
    );
  }

  return (
    <div className="card settings-section">
      <h2>{t("monitor.heading")}</h2>
      <p className="muted">{t("monitor.description")}</p>

      {healthError && (
        <div className="banner banner-error" style={{ marginTop: 12 }}>
          {healthError}
        </div>
      )}

      {health && (
        <>
          <div className="monitor-metrics">
            <MonitorMetric label={t("monitor.cpu")} percent={health.cpu_percent} />
            <MonitorMetric
              label={t("monitor.memory")}
              percent={health.memory_percent}
              detail={t("monitor.memoryDetail", {
                used: health.memory_used_mb,
                total: health.memory_total_mb,
              })}
            />
            <MonitorMetric
              label={t("monitor.disk")}
              percent={health.disk_percent}
              detail={t("monitor.diskDetail", {
                used: health.disk_used_gb,
                total: health.disk_total_gb,
              })}
            />
          </div>

          <p className="muted" style={{ marginTop: 12 }}>
            {t("monitor.uptime", { uptime: formatUptime(health.uptime_seconds) })}
          </p>

          <div className="monitor-services">
            <span className={`monitor-service-badge ${health.mongo_ok ? "ok" : "down"}`}>
              MongoDB {health.mongo_ok ? "●" : "✕"}
            </span>
            {health.services.map((service) => (
              <span
                key={service.name}
                className={`monitor-service-badge ${
                  service.active === true ? "ok" : service.active === false ? "down" : "unknown"
                }`}
              >
                {service.name} {service.active === true ? "●" : service.active === false ? "✕" : "?"}
              </span>
            ))}
          </div>
        </>
      )}

      <hr style={{ margin: "20px 0", border: "none", borderTop: "1px solid var(--border)" }} />

      <div style={{ display: "flex", flexWrap: "wrap", gap: 24 }}>
        <div>
          <button
            type="button"
            className="btn"
            onClick={restartService}
            disabled={restartStatus === "restarting"}
          >
            {t(restartStatus === "restarting" ? "monitor.restarting" : "monitor.restartService")}
          </button>
          {restartStatus === "done" && (
            <p className="muted" style={{ marginTop: 6 }}>
              {t("monitor.restartServiceDone")}
            </p>
          )}
          {restartStatus === "error" && (
            <div className="banner banner-error" style={{ marginTop: 6 }}>
              {restartError}
            </div>
          )}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 10, maxWidth: 320 }}>
          <input
            type="password"
            value={rebootPassword}
            onChange={(e) => setRebootPassword(e.target.value)}
            placeholder={t("monitor.rebootPasswordPlaceholder")}
            autoComplete="current-password"
          />
          <button
            type="button"
            className="btn"
            onClick={rebootServer}
            disabled={!rebootPassword || rebootStatus === "rebooting"}
          >
            {t(rebootStatus === "rebooting" ? "monitor.rebooting" : "monitor.rebootServer")}
          </button>
          {rebootStatus === "done" && <p className="muted">{t("monitor.rebootDone")}</p>}
          {rebootStatus === "timeout" && <p className="muted">{t("monitor.rebootTimeout")}</p>}
          {rebootStatus === "error" && <div className="banner banner-error">{rebootError}</div>}
        </div>
      </div>
    </div>
  );
}

function DeploySection() {
  const t = useT();
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
    const triggeredAt = Date.now();

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
      // BUGS.md #36 — hvis der intet nyt var at hente, ændrer build-nummeret
      // sig aldrig, så det alene kan ikke afgøre succes. Tjek også det
      // eksplicitte deploy-udfald, og kun betragt det som friskt (fra
      // *dette* klik, ikke et efterladt udfald fra sidste gang) hvis det
      // blev skrevet efter vi klikkede.
      try {
        const deployStatus = await api.getDeployStatus();
        const writtenAt = deployStatus.at ? new Date(deployStatus.at).getTime() : 0;
        if (deployStatus.outcome === "up-to-date" && writtenAt >= triggeredAt) {
          clearInterval(poll);
          setStatus("up-to-date");
          return;
        }
      } catch {
        // Statusfil findes muligvis ikke endnu (fx før scripts/deploy.sh er
        // opdateret i produktion) — falder tilbage til build-polling nedenfor.
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
      <h2>{t("deploy.heading")}</h2>
      <p className="muted">
        {t("deploy.description")}
        {currentBuild && t("deploy.currentBuild", { build: currentBuild })}
      </p>

      <button
        type="button"
        className="btn btn-primary"
        onClick={deploy}
        disabled={status === "deploying"}
      >
        {t(status === "deploying" ? "deploy.deploying" : "deploy.deploy")}
      </button>

      {status === "error" && (
        <div className="banner banner-error" style={{ marginTop: 12 }}>
          {error}
        </div>
      )}
      {status === "timeout" && (
        <div className="banner banner-error" style={{ marginTop: 12 }}>
          {t("deploy.timeout")}
        </div>
      )}
      {status === "up-to-date" && (
        <div className="banner banner-info" style={{ marginTop: 12 }}>
          {t("deploy.upToDate", { build: currentBuild })}
        </div>
      )}
      {status === "done" && (
        <div className="banner banner-info" style={{ marginTop: 12 }}>
          {t("deploy.done", { build: currentBuild })}
        </div>
      )}
    </div>
  );
}

// Exporteret til test (regel 19) — tilstands-skiftet omkring
// adgangskode-nulstilling (feature #171) er ellers kun nået via hele
// Settings-siden.
export function UsersSection({ currentUserId }) {
  const t = useT();
  const [users, setUsers] = useState([]);
  const [status, setStatus] = useState("loading");
  const [updatingId, setUpdatingId] = useState(null);
  const [error, setError] = useState(null);
  // Feature #171 — admin-assisteret adgangskode-nulstilling. Adgangskoden
  // findes kun i denne state, aldrig gemt/logget nogen steder; forsvinder
  // ved næste nulstilling, sideskift eller genindlæsning.
  const [resetResult, setResetResult] = useState(null);
  const [passwordCopied, setPasswordCopied] = useState(false);
  // BUGS.md #74 — banneret (nedenfor) renderes øverst i sektionen, over
  // bruger-listen. Med mange brugere er admin typisk scrollet langt ned for
  // overhovedet at kunne se/klikke den række der udløste handlingen, så
  // banneret dukkede op langt uden for skærmen uden nogen antydning af at
  // noget var sket. Scrolles nu automatisk i syne, uanset hvilken handling
  // (nulstilling, rolle, status, sletning) der udløste den.
  const bannerRef = useRef(null);

  useEffect(() => {
    if (resetResult || error) {
      bannerRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [resetResult, error]);

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

  async function changeRole(targetUser, nextRole) {
    if (nextRole === targetUser.role) return;
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

  async function resetPassword(targetUser) {
    if (!window.confirm(t("users.confirmResetPassword", { username: targetUser.username }))) {
      return;
    }
    setUpdatingId(targetUser.id);
    setError(null);
    setPasswordCopied(false);
    try {
      const result = await api.resetUserPassword(targetUser.id);
      setResetResult({ username: result.username, password: result.new_password });
    } catch (err) {
      setError(err.message);
    } finally {
      setUpdatingId(null);
    }
  }

  function copyResetPassword() {
    if (!resetResult) return;
    navigator.clipboard
      .writeText(resetResult.password)
      .then(() => {
        setPasswordCopied(true);
        setTimeout(() => setPasswordCopied(false), 2000);
      })
      .catch(() => {});
  }

  async function deleteUser(targetUser) {
    if (!window.confirm(t("users.confirmDelete", { username: targetUser.username }))) {
      return;
    }
    setUpdatingId(targetUser.id);
    setError(null);
    try {
      await api.deleteUser(targetUser.id);
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
      <h2>{t("users.heading")}</h2>
      <p className="muted">
        {t("users.description")}
        {pendingCount > 0 && t("users.pendingCount", { count: pendingCount })}.
      </p>

      {status === "loading" && <p className="muted">{t("common.loading")}</p>}
      {status === "error" && (
        <div className="banner banner-error">{t("users.loadError")}</div>
      )}
      <div ref={bannerRef}>
        {error && <div className="banner banner-error">{error}</div>}

        {resetResult && (
          <div className="banner banner-info" style={{ alignItems: "flex-start" }}>
            <div style={{ flex: 1 }}>
              <p style={{ margin: 0 }}>
                {t("users.resetPasswordResult", { username: resetResult.username })}
              </p>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  marginTop: 8,
                }}
              >
                <code style={{ fontSize: "1rem", userSelect: "all" }}>{resetResult.password}</code>
                <button type="button" className="btn" onClick={copyResetPassword}>
                  {t(passwordCopied ? "users.passwordCopied" : "users.copyPassword")}
                </button>
              </div>
              <p className="muted" style={{ margin: "8px 0 0" }}>
                {t("users.resetPasswordHint")}
              </p>
            </div>
            <button type="button" className="btn" onClick={() => setResetResult(null)}>
              {t("common.close")}
            </button>
          </div>
        )}
      </div>

      {status === "ready" && (
        <ul className="user-list">
          {users.map((u) => (
            <li key={u.id} className="user-row">
              <span className="user-row-name">
                {u.username}
                {/* Feature #140 — fulde navn, så admin ser hvem der beder om adgang. */}
                {u.full_name && <span className="muted"> · {u.full_name}</span>}
                {u.id === currentUserId && <span className="muted">{t("users.you")}</span>}
              </span>
              {u.status === "pending" && (
                <span className="role-badge">{t("users.statusPending")}</span>
              )}
              {u.status === "rejected" && (
                <span className="role-badge">{t("users.statusRejected")}</span>
              )}
              {u.status === "disabled" && (
                <span className="role-badge">{t("users.statusDisabled")}</span>
              )}
              {u.status === "active" && (
                <span className="role-badge">
                  {t(
                    u.role === "admin"
                      ? "account.roleAdmin"
                      : u.role === "guest"
                        ? "account.roleGuest"
                        : "account.roleStandard"
                  )}
                </span>
              )}
              {u.status === "pending" ? (
                <>
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={updatingId === u.id}
                    onClick={() => setStatusFor(u, "active")}
                  >
                    {updatingId === u.id ? "..." : t("users.approve")}
                  </button>
                  <button
                    type="button"
                    className="btn"
                    disabled={updatingId === u.id}
                    onClick={() => setStatusFor(u, "rejected")}
                  >
                    {t("users.reject")}
                  </button>
                </>
              ) : u.status === "active" ? (
                <>
                  <select
                    value={u.role}
                    disabled={u.id === currentUserId || updatingId === u.id}
                    onChange={(e) => changeRole(u, e.target.value)}
                  >
                    <option value="admin">{t("account.roleAdmin")}</option>
                    <option value="standard">{t("account.roleStandard")}</option>
                    <option value="guest">{t("users.roleGuestOption")}</option>
                  </select>
                  {u.id !== currentUserId && (
                    <button
                      type="button"
                      className="btn"
                      disabled={updatingId === u.id}
                      onClick={() => setStatusFor(u, "disabled")}
                    >
                      {t("users.disable")}
                    </button>
                  )}
                </>
              ) : u.status === "disabled" ? (
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={updatingId === u.id}
                  onClick={() => setStatusFor(u, "active")}
                >
                  {updatingId === u.id ? "..." : t("users.reactivate")}
                </button>
              ) : null}
              {/* Feature #171 — kun meningsfuldt for konti der reelt kan logge
                  ind (aktive/deaktiverede); afventende/afviste har ingen
                  "kontakt brugeren om den nye kode"-situation endnu. */}
              {u.id !== currentUserId && (u.status === "active" || u.status === "disabled") && (
                <button
                  type="button"
                  className="btn"
                  disabled={updatingId === u.id}
                  onClick={() => resetPassword(u)}
                >
                  {t("users.resetPassword")}
                </button>
              )}
              {u.id !== currentUserId && (
                <button
                  type="button"
                  className="btn"
                  disabled={updatingId === u.id}
                  onClick={() => deleteUser(u)}
                >
                  {t("common.delete")}
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
