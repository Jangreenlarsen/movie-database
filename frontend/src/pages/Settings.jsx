import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import AnnouncementQueueSection from "../components/AnnouncementQueue";
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
    // Feature #226 — "Dine beskeder" gælder alle roller; kun de to
    // afsender-sektioner længere nede i selve fanen er stadig admin-only.
    { id: "beskeder", labelKey: "settings.tab.messages", visible: true },
    { id: "konto", labelKey: "settings.tab.account", visible: true },
    { id: "nyt", labelKey: "settings.tab.whatsNew", visible: true },
    { id: "bibliotek", labelKey: "settings.tab.library", visible: !isGuest },
    { id: "biograf", labelKey: "settings.tab.cinema", visible: !isGuest },
    { id: "backup", labelKey: "settings.tab.backup", visible: isAdmin },
    { id: "noegler", labelKey: "settings.tab.keys", visible: isAdmin },
    { id: "drift", labelKey: "settings.tab.ops", visible: isAdmin },
  ].filter((tab) => tab.visible);
}

export default function Settings({ user, onSettingsChanged, initialTab }) {
  const t = useT();
  const isAdmin = user.role === "admin";
  const isGuest = user.role === "guest";
  const tabs = settingsTabs(isAdmin, isGuest);
  // Feature #228 — `initialTab` lader fx påmindelsen om den samlede
  // opdatering åbne direkte på Beskeder. Kun en fane rollen faktisk kan se.
  const [activeTab, setActiveTab] = useState(
    tabs.some((tab) => tab.id === initialTab) ? initialTab : (tabs[0]?.id ?? "konto")
  );

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
          <PasswordPolicySection />
          <AuditLogSection />
        </>
      )}

      {activeTab === "beskeder" && (
        <>
          <MyMessagesSection />
          {/* Feature #228 — fælles kø for admin + standard, ikke gæster. */}
          {!isGuest && <AnnouncementQueueSection />}
          {isAdmin && (
            <>
              <MessagesSection currentUserId={user.id} />
              <MessagePreviewSection />
            </>
          )}
        </>
      )}

      {activeTab === "konto" && (
        <>
          <AccountSection user={user} onSettingsChanged={onSettingsChanged} />
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
          {isAdmin && <PlexImportSection />}
          {isAdmin && <PlexAutoImportSection />}
        </>
      )}

      {activeTab === "biograf" && !isGuest && (
        <>
          <CinemaHistorySection />
          {isAdmin && <ScreeningRequestPolicySection />}
        </>
      )}

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
        </>
      )}

      {activeTab === "drift" && isAdmin && (
        <>
          <TestModeSection />
          <MonitorSection />
          <DeploySection />
          <TlsCertSection />
          <AnthemDiagnosticsSection />
        </>
      )}
    </section>
  );
}

// Feature #197 — navngivet export, kun til test (regel 19), samme mønster
// som UsersSection/PlexShieldSettingsRow.
export function AccountSection({ user, onSettingsChanged }) {
  const t = useT();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(null);

  // Feature #197 — brugerens egen e-mail, kun brugt til udgående
  // notifikationer. Egen lille gem-tilstand, adskilt fra password-formen
  // ovenfor (to uafhængige handlinger, ikke ét samlet "gem alt"-tryk).
  const [email, setEmail] = useState(user.email ?? "");
  const [emailSaving, setEmailSaving] = useState(false);
  const [emailSaved, setEmailSaved] = useState(false);
  const [emailError, setEmailError] = useState(null);

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

  async function saveEmail(event) {
    event.preventDefault();
    setEmailSaving(true);
    setEmailSaved(false);
    setEmailError(null);
    try {
      const updated = await api.updateMyEmail(user.id, email.trim() || null);
      onSettingsChanged(updated);
      setEmailSaved(true);
    } catch (err) {
      setEmailError(err.message);
    } finally {
      setEmailSaving(false);
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

      <form className="serial-config-form" onSubmit={saveEmail} style={{ marginBottom: 20 }}>
        <label>
          {t("account.email")}
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder={t("account.emailPlaceholder")}
          />
        </label>
        <p className="muted" style={{ margin: 0 }}>
          {t("account.emailHint")}
        </p>

        {emailError && <div className="banner banner-error">{emailError}</div>}
        {emailSaved && <div className="banner banner-info">{t("account.emailSaved")}</div>}

        <button type="submit" className="btn btn-primary" disabled={emailSaving}>
          {t(emailSaving ? "common.saving" : "account.saveEmail")}
        </button>
      </form>

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
            // Feature #174 — intet klientside minLength: grænsen er nu
            // admin-konfigurerbar, og en almindelig bruger (ikke-admin) har
            // ingen adgang til at læse den (admin-only endpoint). Backendens
            // field-validator håndhæver den reelle politik; se err.message.
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
            // Bevidst tavs: kopiering er en genvej; teksten står synlig ovenfor.
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

export function SerialNumberSection({ isAdmin }) {
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
  // Feature #188 (retter BUGS.md #81) — engangs-omnummerering af D#-serien.
  const [renumbering, setRenumbering] = useState(false);
  const [renumberResult, setRenumberResult] = useState(null);
  const [renumberError, setRenumberError] = useState(null);

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

  async function renumberDigital() {
    if (!window.confirm(t("serial.confirmRenumberDigital"))) return;
    setRenumbering(true);
    setRenumberResult(null);
    setRenumberError(null);
    try {
      const result = await api.renumberDigitalSerialNumbers();
      setRenumberResult(result.renumbered);
      // Genindlæs "Ledige numre"-oversigten, så den nye, sammenhængende
      // D#-serie fra 1 vises med det samme.
      const updated = await api.getSerialNumberConfig();
      applyConfig(updated);
    } catch (err) {
      setRenumberError(err.message);
    } finally {
      setRenumbering(false);
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

          {/* Feature #188 (retter BUGS.md #81) — engangs-omnummerering af
              D#-serien til at starte fra 1. Rører aldrig M#/T#. */}
          {isAdmin && (
            <div className="serial-renumber-digital">
              <button
                type="button"
                className="btn"
                onClick={renumberDigital}
                disabled={renumbering}
              >
                {t(renumbering ? "serial.renumberingDigital" : "serial.renumberDigital")}
              </button>
              <p className="muted serial-reuse-hint">{t("serial.renumberDigitalHint")}</p>
              {renumberError && <div className="banner banner-error">{renumberError}</div>}
              {renumberResult != null && (
                <div className="banner banner-info">
                  {t("serial.renumberDigitalDone", { count: renumberResult })}
                </div>
              )}
            </div>
          )}

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
//
// BUGS.md #86 (Jan, 2026-08-22: "under settings/bibliotek/Serienummer-
// opsætning skal vi have serie nr. i en dropdown liste fordi hvis der er
// mange nr. ikke i brug bliver den liste meget stor") — var før en
// kommasepareret tekststreng der voksede ubegrænset og ombrød grimt ved
// mange ledige numre; en `<select>` holder rækken kompakt uanset antal, og
// lader admin selv folde listen ud og bladre i den. Backend'en begrænser nu
// selv listen til de laveste 100 (samme sag) — `numbers.length` kan derfor
// aldrig være voldsomt stor, men dropdown'en er stadig den rigtige
// visningsform uanset hvor mange der reelt er ledige.
function SerialFreeList({ label, numbers, prefix, t }) {
  return (
    <div className="serial-free-row">
      <span className="serial-free-label">{label}</span>
      {numbers.length > 0 ? (
        <span className="serial-free-values">
          <select className="serial-free-select" aria-label={label} defaultValue="">
            <option value="" disabled>
              {t("serial.freeNumbers")} ({numbers.length})
            </option>
            {numbers.map((n) => (
              <option key={n} value={n}>
                {`${prefix}#${n}`}
              </option>
            ))}
          </select>
          {/* Feature #86 — samme loft som backend'ens MAX_FREE_NUMBERS (100);
              rammes det præcis, er der formentlig flere end vist. */}
          {numbers.length >= 100 && (
            <span className="muted serial-free-capped-hint">
              {t("serial.freeNumbersCapped", { count: numbers.length })}
            </span>
          )}
        </span>
      ) : (
        <span className="serial-free-values">{t("serial.freeNone")}</span>
      )}
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

// Feature #197 — navngivet export, kun til test (regel 19), samme mønster
// som UsersSection/PlexShieldSettingsRow.
export function SystemSettingsSection() {
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
    <>
      <div className="card settings-section">
        <h2>{t("sys.heading")}</h2>
        <p className="muted">{t("sys.description")}</p>

        {loadStatus === "loading" && <p className="muted">{t("common.loading")}</p>}
        {loadStatus === "error" && (
          <div className="banner banner-error">{t("sys.statusError")}</div>
        )}
      </div>

      {loadStatus === "ready" && statusData && (
        <>
          {/* Feature #197-opfølgning (Jan: "få lige orginaseret den config
              side at det hele ikke kommer i en lang smøre") — de ~13 rækker
              stod tidligere i ét langt, ugrupperet kort. Opdelt i selvstændige
              kort efter FORMÅL (samme mønster resten af Indstillinger-siden
              allerede bruger — hvert kort er sin egen afgrænsede ting), ikke
              alfabetisk eller efter hvornår nøglen blev tilføjet. */}
          <div className="card settings-section">
            <h2>{t("sys.groupMetadata")}</h2>
            <ApiKeyRow
              label="TMDb API-token"
              field="tmdb_api_token"
              status={statusData.tmdb_api_token}
              onSaved={load}
            />
          </div>

          <div className="card settings-section">
            <h2>{t("sys.groupBarcode")}</h2>
            <p className="muted">{t("sys.groupBarcodeDescription")}</p>
            <PrimaryBarcodeSourceRow
              currentValue={statusData.primary_barcode_source}
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
          </div>

          <div className="card settings-section">
            <h2>{t("sys.groupRatings")}</h2>
            <ApiKeyRow
              label={t("sys.omdbKey")}
              field="omdb_api_key"
              status={statusData.omdb_api_key}
              onSaved={load}
            />
          </div>

          <div className="card settings-section">
            <h2>{t("sys.groupPlex")}</h2>
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
            <PlexShieldSettingsRow
              currentValue={statusData.plex_shield_client_identifier}
              onSaved={load}
            />
          </div>

          <div className="card settings-section">
            <h2>{t("sys.groupAnthem")}</h2>
            <PlainSettingRow
              label={t("sys.anthemHost")}
              field="anthem_host"
              hint={t("sys.anthemHostHint")}
              currentValue={statusData.anthem_host}
              onSaved={load}
            />
            <PlainSettingRow
              label={t("sys.anthemPort")}
              field="anthem_port"
              hint={t("sys.anthemPortHint")}
              currentValue={statusData.anthem_port}
              onSaved={load}
            />
            <AnthemTestConnectionRow />
          </div>

          <div className="card settings-section">
            <h2>{t("sys.groupEmail")}</h2>
            <p className="muted">{t("sys.groupEmailDescription")}</p>
            <ApiKeyRow
              label={t("sys.resendKey")}
              field="resend_api_key"
              status={statusData.resend_api_key}
              onSaved={load}
            />
            <PlainSettingRow
              label={t("sys.emailFromAddress")}
              field="email_from_address"
              hint={t("sys.emailFromAddressHint")}
              currentValue={statusData.email_from_address}
              onSaved={load}
            />
            <SendTestEmailRow />
          </div>
        </>
      )}
    </>
  );
}

/**
 * Feature #178 (Jan: "når man trykker på vis i plex så er option at starte
 * den i plex på shield der også") — admin-opsætningen der finder og gemmer
 * Shield TV'ets Plex client-id. Skiller sig fra `PlainSettingRow` ved at
 * tilbyde en "Hent tilgængelige klienter"-liste i stedet for et frit
 * tekstfelt: id'et er en uigennemskuelig GUID, ikke noget en admin realistisk
 * kan skrive selv.
 */
export function PlexShieldSettingsRow({ currentValue, onSaved }) {
  const t = useT();
  const [clientsStatus, setClientsStatus] = useState("idle"); // idle | loading | done | error
  const [clients, setClients] = useState([]);
  // BUGS.md #76 (Jan: "der skal nok noget feedback til så man kan se at din
  // code gør det korekte") — hvor mange entries PMS selv rapporterede i alt,
  // uafhængigt af hvor mange der kunne bruges. Lader Jan se om et tomt
  // resultat er Plex' eget svar (0 i alt — bekræftet en Plex-/
  // netværksbegrænsning) eller noget der blev filtreret forkert her.
  const [rawEntryCount, setRawEntryCount] = useState(0);
  const [clientsError, setClientsError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  async function fetchClients() {
    setClientsStatus("loading");
    setClientsError(null);
    try {
      const result = await api.getPlexClients();
      if (result.ok) {
        setClients(result.items);
        setRawEntryCount(result.raw_entry_count);
        setClientsStatus("done");
      } else {
        setClientsStatus("error");
        setClientsError(result.error);
      }
    } catch (err) {
      setClientsStatus("error");
      setClientsError(err.message);
    }
  }

  async function selectClient(machineIdentifier) {
    setSaving(true);
    setSaveError(null);
    try {
      await api.updateSystemSettings({ plex_shield_client_identifier: machineIdentifier });
      onSaved();
    } catch (err) {
      setSaveError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="serial-config-form" style={{ marginBottom: 16 }}>
      <strong>{t("plexShieldSettings.heading")}</strong>
      <p className="muted">{t("plexShieldSettings.description")}</p>
      <p className="muted">
        {currentValue
          ? t("plexShieldSettings.currentIdentifier", { id: currentValue })
          : t("plexShieldSettings.selectedNone")}
      </p>

      <button
        type="button"
        className="btn"
        onClick={fetchClients}
        disabled={clientsStatus === "loading"}
      >
        {t(
          clientsStatus === "loading"
            ? "plexShieldSettings.fetchingClients"
            : "plexShieldSettings.fetchClients"
        )}
      </button>

      {clientsStatus === "error" && <div className="banner banner-error">{clientsError}</div>}
      {clientsStatus === "done" && clients.length === 0 && rawEntryCount === 0 && (
        <p className="muted">{t("plexShieldSettings.noClientsFound")}</p>
      )}
      {clientsStatus === "done" && clients.length === 0 && rawEntryCount > 0 && (
        <div className="banner banner-error">
          {t("plexShieldSettings.clientsFilteredOut", { count: rawEntryCount })}
        </div>
      )}
      {clientsStatus === "done" && clients.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 8 }}>
          {clients.map((c) => (
            <button
              key={c.machine_identifier}
              type="button"
              className={c.machine_identifier === currentValue ? "btn btn-primary" : "btn"}
              onClick={() => selectClient(c.machine_identifier)}
              disabled={saving}
              style={{ alignSelf: "flex-start" }}
            >
              {c.name}
              {c.product ? ` (${c.product})` : ""}
            </button>
          ))}
        </div>
      )}
      {saveError && <div className="banner banner-error">{saveError}</div>}
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
export function PlexImportSection() {
  const t = useT();
  const [includeMovies, setIncludeMovies] = useState(true);
  const [includeShows, setIncludeShows] = useState(true);
  const [tag, setTag] = useState("Plex-import");
  // BUGS.md #111 — fejler indlæsningen af det gemte tag, står standard-
  // værdien i feltet, og en rigtig import gemmer den som det delte tag.
  // Advar derfor tydeligt i stedet for stille at vise standarden.
  const [tagLoadError, setTagLoadError] = useState(null);
  const [status, setStatus] = useState("idle"); // idle | previewing | preview | importing | done | error
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  // Jan: "søger for at tag på importerede i auto-scan plex er det tag som
  // er difineret under 'importer fra plex'" — denne sektion definerer det
  // delte tag, så indlæs den faktisk gældende værdi i stedet for altid at
  // starte forfra på "Plex-import". Fejler indlæsningen, beholdes den
  // hårdkodede default — samme fallback som feltet altid har haft.
  useEffect(() => {
    api
      .getPlexAutoImportPolicy()
      .then((policy) => setTag(policy.plex_import_tag))
      .catch((err) => setTagLoadError(err.message));
  }, []);

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
        {tagLoadError && (
          <div className="banner banner-error" style={{ marginTop: 8 }}>
            {t("plexImport.tagLoadFailed", { message: tagLoadError })}
          </div>
        )}
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
 * Feature #226 (Jan: "hvis en bruger ikke har være login i lang tid så kan
 * det være at han har 1000 beskeder kondesere dem til max 3 besked med
 * meddelese om at ham kan gå under instillinger/besked og se alle og
 * slette alle hams beskeder") — modstykket til `MessageBanner`s
 * 3-bannere-loft: her kan enhver (ikke kun admin) se sit FULDE ulæste
 * efterslæb og rydde det på én gang. "Rydning" markerer dem som læst
 * (samme felt som at lukke et banner) — der findes ingen separat
 * "slettet"-tilstand, og admins "Sendte beskeder"-oversigt skal stadig
 * kunne se at beskeden blev læst, bare ikke hvornår brugeren fandt tid.
 */
export function MyMessagesSection() {
  const t = useT();
  const locale = useLocale();
  const [messages, setMessages] = useState([]);
  const [loaded, setLoaded] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [page, setPage] = useState(0);
  const [clearing, setClearing] = useState(false);
  const [dismissing, setDismissing] = useState(null);
  const [error, setError] = useState(null);

  function load() {
    api
      .getInbox()
      .then((fresh) => {
        setMessages(fresh);
        setLoaded(true);
      })
      .catch((err) => setError(err.message));
  }

  useEffect(load, []);

  async function clearAll() {
    if (!window.confirm(t("myMessages.confirmClearAll", { count: messages.length }))) return;
    setClearing(true);
    setError(null);
    try {
      await api.markAllMessagesRead();
      setMessages([]);
    } catch (err) {
      setError(err.message);
    } finally {
      setClearing(false);
    }
  }

  async function dismissOne(messageId) {
    setDismissing(messageId);
    setError(null);
    try {
      await api.markMessageRead(messageId);
      setMessages((prev) => prev.filter((m) => m.id !== messageId));
    } catch (err) {
      setError(err.message);
    } finally {
      setDismissing(null);
    }
  }

  const totalPages = Math.max(1, Math.ceil(messages.length / SENT_MESSAGES_PAGE_SIZE));
  const clampedPage = Math.min(page, totalPages - 1);
  const pagedMessages = messages.slice(
    clampedPage * SENT_MESSAGES_PAGE_SIZE,
    clampedPage * SENT_MESSAGES_PAGE_SIZE + SENT_MESSAGES_PAGE_SIZE
  );

  return (
    <div className="card settings-section">
      <h2>{t("myMessages.heading")}</h2>
      <p className="muted">{t("myMessages.description")}</p>

      {error && <div className="banner banner-error">{error}</div>}

      {loaded && messages.length === 0 ? (
        <p className="muted">{t("myMessages.none")}</p>
      ) : (
        loaded && (
          <>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
              <strong>{t("myMessages.unreadCount", { count: messages.length })}</strong>
              <button type="button" className="btn btn-primary" onClick={clearAll} disabled={clearing}>
                {t(clearing ? "myMessages.clearing" : "myMessages.clearAll")}
              </button>
            </div>

            <button
              type="button"
              className="settings-collapsible-toggle"
              style={{ marginTop: 16 }}
              onClick={() => setExpanded((prev) => !prev)}
              aria-expanded={expanded}
            >
              <h3 style={{ margin: 0 }}>{t("myMessages.listHeading")}</h3>
              <span aria-hidden="true">{expanded ? "▾" : "▸"}</span>
            </button>

            {expanded && (
              <>
                <ul className="user-list">
                  {pagedMessages.map((message) => (
                    <li key={message.id} className="message-sent-row">
                      <div className="message-sent-main">
                        <strong>{message.subject}</strong>
                        <div className="muted message-sent-meta">{message.body}</div>
                        <div className="muted message-sent-meta">
                          {t("messages.from", {
                            sender: message.sent_by,
                            date: new Date(message.created_at).toLocaleDateString(locale),
                          })}
                        </div>
                      </div>
                      <button
                        type="button"
                        className="btn"
                        onClick={() => dismissOne(message.id)}
                        disabled={dismissing === message.id}
                      >
                        {t(dismissing === message.id ? "messages.dismissing" : "messages.dismiss")}
                      </button>
                    </li>
                  ))}
                </ul>

                {messages.length > SENT_MESSAGES_PAGE_SIZE && (
                  <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 12 }}>
                    <button
                      type="button"
                      className="btn"
                      onClick={() => setPage(clampedPage - 1)}
                      disabled={clampedPage === 0}
                    >
                      {t("messages.previous")}
                    </button>
                    <span className="muted">
                      {t("messages.page", { page: clampedPage + 1, totalPages })}
                    </span>
                    <button
                      type="button"
                      className="btn"
                      onClick={() => setPage(clampedPage + 1)}
                      disabled={clampedPage + 1 >= totalPages}
                    >
                      {t("messages.next")}
                    </button>
                  </div>
                )}
              </>
            )}
          </>
        )
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
// Feature #224 — Jan: "gør det til en list som default skal udfoldet og
// med max 10 entry par side i den liste". Client-side paginering: hele
// listen hentes stadig i ét kald (som hidtil, api.listMessages() har ingen
// skip/limit), kun VISNINGEN begrænses til 10 ad gangen — ingen ny
// backend-kontrakt nødvendig for den beskedne mængde beskeder en
// admin-portal som denne reelt ophober.
const SENT_MESSAGES_PAGE_SIZE = 10;

export function MessagesSection({ currentUserId }) {
  const t = useT();
  const locale = useLocale();
  const [users, setUsers] = useState([]);
  const [messages, setMessages] = useState([]);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [recipient, setRecipient] = useState("");
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState(null);
  // Feature #224 — default UDFOLDET (Jans eksplicitte ønske), til forskel
  // fra #223s nye "Sådan ser beskederne ud"-sektion, som default er
  // sammenfoldet (den er ny og mindre central end selve besked-historikken).
  const [sentExpanded, setSentExpanded] = useState(true);
  const [sentPage, setSentPage] = useState(0);

  function load() {
    api.listMessages().then(setMessages).catch((err) => setError(err.message));
    // BUGS.md #111 — uden brugerlisten er modtager-vælgeren tom; vis hvorfor.
    api.listUsers().then(setUsers).catch((err) => setError(err.message));
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

  // Feature #224 — client-side paginering af den allerede hentede liste.
  // `clampedSentPage` beskytter mod at stå tilbage på en tom side, hvis en
  // sletning (eller en genindlæsning med færre beskeder) gør den tidligere
  // valgte side ude af rækkevidde.
  const sentTotalPages = Math.max(1, Math.ceil(messages.length / SENT_MESSAGES_PAGE_SIZE));
  const clampedSentPage = Math.min(sentPage, sentTotalPages - 1);
  const pagedMessages = messages.slice(
    clampedSentPage * SENT_MESSAGES_PAGE_SIZE,
    clampedSentPage * SENT_MESSAGES_PAGE_SIZE + SENT_MESSAGES_PAGE_SIZE
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

      <button
        type="button"
        className="settings-collapsible-toggle"
        onClick={() => setSentExpanded((prev) => !prev)}
        aria-expanded={sentExpanded}
      >
        <h3 style={{ margin: 0 }}>{t("messages.sentHeading")}</h3>
        <span aria-hidden="true">{sentExpanded ? "▾" : "▸"}</span>
      </button>

      {sentExpanded && (
        <>
          {messages.length === 0 ? (
            <p className="muted">{t("messages.noneSent")}</p>
          ) : (
            <>
              <ul className="user-list">
                {pagedMessages.map((message) => (
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

              {messages.length > SENT_MESSAGES_PAGE_SIZE && (
                <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 12 }}>
                  <button
                    type="button"
                    className="btn"
                    onClick={() => setSentPage(clampedSentPage - 1)}
                    disabled={clampedSentPage === 0}
                  >
                    {t("messages.previous")}
                  </button>
                  <span className="muted">
                    {t("messages.page", { page: clampedSentPage + 1, totalPages: sentTotalPages })}
                  </span>
                  <button
                    type="button"
                    className="btn"
                    onClick={() => setSentPage(clampedSentPage + 1)}
                    disabled={clampedSentPage + 1 >= sentTotalPages}
                  >
                    {t("messages.next")}
                  </button>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}

/**
 * Feature #223 (Jan: "hvordan kan jeg se hvordan en besked se ud, kan vi
 * lave en besked design editor hvor alle de besked typer som er i spil
 * kan se og edit") — katalog: vælg en besked-type i listen for at se
 * hvordan den ser ud, både den korte tekst man ser i appen
 * (banner/indbakke) og den rigere e-mail-udgave. Hentet lazily første
 * gang sektionen foldes ud, ikke ved hvert besøg på Indstillinger-siden.
 *
 * Feature #225 (samme citat, anden halvdel: "... og edit") — selve
 * redigeringen. Kun typer med `editable: true` (alle undtagen de 5 faste
 * "afstemning aflyst"-vittigheds-varianter, se message_service.py) viser
 * en "Redigér"-knap. Gem/nulstil sender kun de RÅ skabelon-felter
 * (stadig med bogstavelige `{pladsholder}`-navne) — den substituerede
 * eksempel-visning ovenfor opdateres med det samme fra samme svar, så man
 * ser effekten uden en ekstra hentning.
 */
export function MessagePreviewSection() {
  const t = useT();
  const [expanded, setExpanded] = useState(false);
  const [previews, setPreviews] = useState([]);
  const [activeKey, setActiveKey] = useState(null);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState(null);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  useEffect(() => {
    if (!expanded || previews.length > 0) return;
    setStatus("loading");
    setError(null);
    api
      .listMessagePreviews()
      .then((data) => {
        setPreviews(data);
        setActiveKey(data[0]?.key ?? null);
        setStatus("idle");
      })
      .catch((err) => {
        setError(err.message);
        setStatus("error");
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expanded]);

  const active = previews.find((p) => p.key === activeKey) ?? null;

  function selectKey(key) {
    setActiveKey(key);
    setEditing(false);
    setSaveError(null);
  }

  function startEditing() {
    setForm({ ...active.template });
    setSaveError(null);
    setEditing(true);
  }

  function replacePreview(updated) {
    setPreviews((prev) => prev.map((p) => (p.key === updated.key ? updated : p)));
  }

  async function saveTemplate(event) {
    event.preventDefault();
    setSaving(true);
    setSaveError(null);
    try {
      const updated = await api.updateMessageTemplate(active.key, form);
      replacePreview(updated);
      setEditing(false);
    } catch (err) {
      setSaveError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function resetTemplate() {
    setSaving(true);
    setSaveError(null);
    try {
      const updated = await api.resetMessageTemplate(active.key);
      replacePreview(updated);
      setEditing(false);
    } catch (err) {
      setSaveError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="card settings-section">
      <button
        type="button"
        className="settings-collapsible-toggle"
        onClick={() => setExpanded((prev) => !prev)}
        aria-expanded={expanded}
      >
        <h2 style={{ margin: 0 }}>{t("messagePreview.heading")}</h2>
        <span aria-hidden="true">{expanded ? "▾" : "▸"}</span>
      </button>
      <p className="muted">{t("messagePreview.description")}</p>

      {expanded && (
        <>
          {status === "loading" && <p className="muted">{t("common.loading")}</p>}
          {error && <div className="banner banner-error">{error}</div>}
          {previews.length > 0 && (
            <div className="message-preview-layout">
              <ul className="message-preview-list">
                {previews.map((preview) => (
                  <li key={preview.key}>
                    <button
                      type="button"
                      className={preview.key === activeKey ? "active" : ""}
                      onClick={() => selectKey(preview.key)}
                    >
                      {preview.name}
                      {preview.is_customized && (
                        <span className="message-preview-customized-dot" title={t("messagePreview.customized")} />
                      )}
                    </button>
                  </li>
                ))}
              </ul>
              {active && (
                <div className="message-preview-detail">
                  <p className="muted">{active.description}</p>

                  {active.editable && !editing && (
                    <div className="message-preview-edit-bar">
                      <button type="button" className="btn" onClick={startEditing}>
                        {t("messagePreview.edit")}
                      </button>
                      {active.is_customized && (
                        <>
                          <span className="message-preview-customized-label">{t("messagePreview.isCustomized")}</span>
                          <button type="button" className="btn" onClick={resetTemplate} disabled={saving}>
                            {t(saving ? "messagePreview.resetting" : "messagePreview.reset")}
                          </button>
                        </>
                      )}
                    </div>
                  )}

                  {editing && form && (
                    <form className="message-preview-edit-form" onSubmit={saveTemplate}>
                      <p className="muted">
                        {t("messagePreview.placeholdersHint", {
                          placeholders: active.placeholders.map((p) => `{${p}}`).join(", "),
                        })}
                      </p>
                      <label>
                        {t("messagePreview.fieldSubject")}
                        <input
                          value={form.subject}
                          onChange={(e) => setForm({ ...form, subject: e.target.value })}
                          required
                        />
                      </label>
                      <label>
                        {t("messagePreview.fieldBody")}
                        <textarea
                          value={form.body}
                          onChange={(e) => setForm({ ...form, body: e.target.value })}
                          rows={3}
                          style={{ resize: "vertical" }}
                          required
                        />
                      </label>
                      {form.headline !== null && (
                        <>
                          <label>
                            {t("messagePreview.fieldHeadline")}
                            <input
                              value={form.headline}
                              onChange={(e) => setForm({ ...form, headline: e.target.value })}
                              required
                            />
                          </label>
                          <label>
                            {t("messagePreview.fieldTagline")}
                            <input
                              value={form.tagline}
                              onChange={(e) => setForm({ ...form, tagline: e.target.value })}
                              required
                            />
                          </label>
                          <label>
                            {t("messagePreview.fieldAccent")}
                            <select
                              value={form.accent}
                              onChange={(e) => setForm({ ...form, accent: e.target.value })}
                            >
                              <option value="gold">{t("messagePreview.accentGold")}</option>
                              <option value="muted">{t("messagePreview.accentMuted")}</option>
                            </select>
                          </label>
                        </>
                      )}
                      {form.cta_label !== null && (
                        <label>
                          {t("messagePreview.fieldCtaLabel")}
                          <input
                            value={form.cta_label}
                            onChange={(e) => setForm({ ...form, cta_label: e.target.value })}
                            required
                          />
                        </label>
                      )}

                      {saveError && <div className="banner banner-error">{saveError}</div>}

                      <div className="message-preview-edit-actions">
                        <button type="submit" className="btn btn-primary" disabled={saving}>
                          {t(saving ? "common.saving" : "common.save")}
                        </button>
                        <button
                          type="button"
                          className="btn"
                          onClick={() => setEditing(false)}
                          disabled={saving}
                        >
                          {t("common.cancel")}
                        </button>
                      </div>
                    </form>
                  )}

                  <div className="message-preview-block">
                    <div className="message-preview-label">{t("messagePreview.inAppLabel")}</div>
                    <div className="message-preview-inapp">
                      <strong>{active.subject}</strong>
                      <p style={{ whiteSpace: "pre-wrap" }}>{active.body}</p>
                    </div>
                  </div>

                  {active.html && (
                    <div className="message-preview-block">
                      <div className="message-preview-label">{t("messagePreview.emailLabel")}</div>
                      <iframe
                        title={active.name}
                        srcDoc={active.html}
                        className="message-preview-frame"
                      />
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </>
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

// Feature #212 (Jan: "kan vi ikke lige få en test funktion ind i api config
// for AVM70 også sådan at vi kan testet den på samme hvilkor som api
// keys") — anthem_host/anthem_port er PLAIN felter (PlainSettingRow, ikke
// ApiKeyRow, da IP/port ikke er en hemmelighed), som ikke selv har noget
// testbegreb. I stedet for at gøre PlainSettingRow generisk testbar for et
// behov kun Anthem har lige nu, er dette en lille, dedikeret række der
// genbruger samme "Test forbindelse"-knap/banner-mønster som ApiKeyRow.
function AnthemTestConnectionRow() {
  const t = useT();
  const [testStatus, setTestStatus] = useState("idle");
  const [testResult, setTestResult] = useState(null);

  async function testConnection() {
    setTestStatus("testing");
    setTestResult(null);
    try {
      const result = await api.testSystemSetting("anthem_host");
      setTestResult(result);
    } catch (err) {
      setTestResult({ ok: false, message: err.message });
    } finally {
      setTestStatus("idle");
    }
  }

  return (
    <div style={{ marginBottom: 16 }}>
      {testResult && (
        <div className={`banner ${testResult.ok ? "banner-info" : "banner-error"}`}>
          {testResult.ok ? "✓" : "✗"} {testResult.message}
        </div>
      )}
      <button type="button" className="btn" onClick={testConnection} disabled={testStatus === "testing"}>
        {t(testStatus === "testing" ? "sys.testing" : "sys.testConnection")}
      </button>
    </div>
  );
}

// Feature #199 (Jan: "lave også en email test funktion") — ægte ende-til-
// ende-afsendelse, adskilt fra Resend-rækkens "Test forbindelse"-knap
// (ApiKeyRow, testable=true ovenfor), som kun bekræfter selve nøglens
// gyldighed — for en "sending access"-nøgle (Resends anbefalede, mindst
// privilegerede type) kan den slet ikke bekræfte mere end det. Egen
// modtager-adresse i stedet for automatisk at bruge admins egen e-mail, så
// den kan bruges før man overhovedet har sat en selv.
export function SendTestEmailRow() {
  const t = useT();
  const [to, setTo] = useState("");
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState(null);

  async function submit(event) {
    event.preventDefault();
    setSending(true);
    setResult(null);
    try {
      const outcome = await api.sendTestEmail(to);
      setResult(outcome);
    } catch (err) {
      setResult({ ok: false, message: err.message });
    } finally {
      setSending(false);
    }
  }

  return (
    <form className="serial-config-form" style={{ marginTop: 16 }} onSubmit={submit}>
      <label>
        {t("sys.testEmailTo")}
        <input
          type="email"
          value={to}
          onChange={(e) => setTo(e.target.value)}
          placeholder={t("account.emailPlaceholder")}
          required
        />
      </label>

      {result && (
        <div className={`banner ${result.ok ? "banner-info" : "banner-error"}`}>
          {result.ok ? "✓" : "✗"} {result.message}
        </div>
      )}

      <button type="submit" className="btn" disabled={sending || !to}>
        {t(sending ? "sys.testEmailSending" : "sys.testEmailSend")}
      </button>
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

// Feature #194 — navngivet eksport, kun til test (regel 19 — samme mønster
// som UsersSection, feature #171).
export function DeploySection() {
  const t = useT();
  const [currentBuild, setCurrentBuild] = useState(null);
  // Feature #194 — Jan: "vi skal have en mulighed for at opdater fra github
  // på Main eller Dev på portal sådan det giver mening med main og dev
  // versioner". "main" er standardvalget (uændret, sikker opførsel).
  const [branch, setBranch] = useState("main");
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState(null);

  useEffect(() => {
    api
      .health()
      .then((data) => setCurrentBuild(data.build))
      // Bevidst tavs: kun visning af nuværende build; opdateringen virker uden.
      .catch(() => {});
  }, []);

  async function deploy() {
    // Samme "bekræft en risikabel handling"-mønster som database-reset/
    // cert-install: kun for dev, da main er den hidtidige, allerede
    // afprøvede standardopførsel og ikke behøver en ekstra bekræftelse.
    if (branch === "dev" && !window.confirm(t("deploy.branchConfirm"))) {
      return;
    }

    setStatus("deploying");
    setError(null);
    const startedFromBuild = currentBuild;
    const triggeredAt = Date.now();

    try {
      await api.triggerDeploy(branch);
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

      <div className="deploy-branch-picker" role="radiogroup" aria-label={t("deploy.branchLabel")}>
        <label>
          <input
            type="radio"
            name="deploy-branch"
            value="main"
            checked={branch === "main"}
            onChange={() => setBranch("main")}
          />
          {t("deploy.branchMain")}
        </label>
        <label>
          <input
            type="radio"
            name="deploy-branch"
            value="dev"
            checked={branch === "dev"}
            onChange={() => setBranch("dev")}
          />
          {t("deploy.branchDev")}
        </label>
      </div>

      {branch === "dev" && (
        <p className="muted deploy-branch-warning">{t("deploy.branchDevWarning")}</p>
      )}

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
  // Feature #206 (#197's afgrænsede "senere"-punkt: "admin redigerer en
  // ANDEN brugers e-mail") — egen lille redigerings-tilstand pr. række,
  // adskilt fra `updatingId` (som dækker rolle/status/nulstilling), da
  // e-mail-redigering har sin egen inputværdi at holde styr på.
  const [editingEmailId, setEditingEmailId] = useState(null);
  const [emailDraft, setEmailDraft] = useState("");
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

  // Feature #178-opfølgning (Jan: "sæt op i users styring hvem kan se og
  // bruge vis iplex/spil i plex i detajle for film/tv") — pr.-bruger, ikke
  // rolle-baseret.
  async function togglePlexPlay(targetUser) {
    setUpdatingId(targetUser.id);
    setError(null);
    try {
      await api.updateUserPlexPlay(targetUser.id, !targetUser.plex_play_enabled);
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
      // Bevidst tavs: kodeordet står synligt i vinduet og kan kopieres manuelt.
      .catch(() => {});
  }

  function startEditEmail(targetUser) {
    setEditingEmailId(targetUser.id);
    setEmailDraft(targetUser.email ?? "");
    setError(null);
  }

  function cancelEditEmail() {
    setEditingEmailId(null);
    setEmailDraft("");
  }

  async function saveEmail(targetUser) {
    setUpdatingId(targetUser.id);
    setError(null);
    try {
      await api.updateMyEmail(targetUser.id, emailDraft.trim() || null);
      setEditingEmailId(null);
      setEmailDraft("");
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setUpdatingId(null);
    }
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
              {/* Feature #206 — admin kan redigere en ANDEN brugers e-mail
                  (backend understøtter det allerede, self-eller-admin, se
                  auth_service._assert_can_edit_email fra feature #197). */}
              {editingEmailId === u.id ? (
                <span className="user-row-email-edit">
                  <input
                    type="email"
                    value={emailDraft}
                    onChange={(e) => setEmailDraft(e.target.value)}
                    placeholder={t("account.emailPlaceholder")}
                    autoFocus
                  />
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={updatingId === u.id}
                    onClick={() => saveEmail(u)}
                  >
                    {t("common.save")}
                  </button>
                  <button type="button" className="btn" onClick={cancelEditEmail}>
                    {t("common.cancel")}
                  </button>
                </span>
              ) : (
                <span className="muted user-row-email">
                  {u.email || t("users.noEmail")}{" "}
                  <button type="button" className="auth-link" onClick={() => startEditEmail(u)}>
                    {t("users.editEmail")}
                  </button>
                </span>
              )}
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
              {/* Feature #178-opfølgning — samme afgrænsning som nulstillings-
                  knappen ovenfor (kun relevant for konti der reelt kan logge
                  ind), men ikke ekskluderet for den nuværende admin selv —
                  ingen lockout-risiko ved at slå sin egen fra. */}
              {(u.status === "active" || u.status === "disabled") && (
                <button
                  type="button"
                  className="btn"
                  disabled={updatingId === u.id}
                  onClick={() => togglePlexPlay(u)}
                >
                  {t(u.plex_play_enabled ? "users.plexPlayEnabled" : "users.plexPlayDisabled")}
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

// Feature #174 — admin-konfigurerbar adgangskode-politik (Jan: "vi skal have
// en password politik config del i setting"). Håndhæves reelt i backend
// (models.user.validate_password_policy, kaldt ved registrering, eget
// skift OG den admin-genererede midlertidige kode fra #171) — denne
// sektion er kun UI'et til at ændre den, samme arbejdsdeling som alle
// andre admin-only indstillinger på siden. Eksporteret til test (regel 19),
// samme begrundelse som UsersSection ovenfor.
// Feature #177 — admin-indstilling: kræv dato/tidspunkt for guests ved
// visningsønsker, til/fra. Standard/admin er ikke omfattet (håndhævet
// unconditionally i backend), så teksten her taler bevidst kun om gæster.
// Feature #181 (Jan: "jeg tro tilgengæld at vi skal have en automatisk
// scan af plex media server for ny film og tv serie, i dag er det en
// manual funktion"). Samme lille sektions-mønster som
// ScreeningRequestPolicySection nedenfor, men med et ekstra numerisk felt
// for intervallet. Den eksisterende manuelle "Importér fra Plex"-knap
// (PlexImportSection ovenfor) forbliver urørt ved siden af.
export function PlexAutoImportSection() {
  const t = useT();
  const [loadStatus, setLoadStatus] = useState("loading");
  const [enabled, setEnabled] = useState(false);
  const [intervalMinutes, setIntervalMinutes] = useState(360);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(null);

  function load() {
    setLoadStatus("loading");
    api
      .getPlexAutoImportPolicy()
      .then((data) => {
        setEnabled(data.plex_auto_import_enabled);
        setIntervalMinutes(data.plex_auto_import_interval_minutes);
        setLoadStatus("ready");
      })
      .catch(() => setLoadStatus("error"));
  }

  useEffect(load, []);

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const updated = await api.updatePlexAutoImportPolicy({
        plex_auto_import_enabled: enabled,
        plex_auto_import_interval_minutes: intervalMinutes,
      });
      setEnabled(updated.plex_auto_import_enabled);
      setIntervalMinutes(updated.plex_auto_import_interval_minutes);
      setSaved(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="card settings-section">
      <h2>{t("plexAutoImport.heading")}</h2>
      <p className="muted">{t("plexAutoImport.description")}</p>

      {loadStatus === "loading" && <p className="muted">{t("common.loading")}</p>}
      {loadStatus === "error" && (
        <div className="banner banner-error">{t("plexAutoImport.loadError")}</div>
      )}

      {loadStatus === "ready" && (
        <form className="serial-config-form" onSubmit={submit}>
          <label className="serial-reuse-toggle">
            <input
              type="checkbox"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
            />
            {t("plexAutoImport.enabled")}
          </label>

          <label>
            {t("plexAutoImport.intervalLabel")}{" "}
            <span className="muted">
              {t("plexAutoImport.intervalHint", {
                hours: (intervalMinutes / 60).toFixed(1).replace(/\.0$/, ""),
              })}
            </span>
            <input
              type="number"
              min={15}
              max={10080}
              value={intervalMinutes}
              onChange={(e) => setIntervalMinutes(Number(e.target.value))}
            />
          </label>

          {error && <div className="banner banner-error">{error}</div>}
          {saved && <div className="banner banner-info">{t("serial.saved")}</div>}

          <button type="submit" className="btn btn-primary" disabled={saving}>
            {t(saving ? "common.saving" : "common.save")}
          </button>
        </form>
      )}
    </div>
  );
}

// Feature #217 (Jan: "vi skal have en funktion for adm i settings hvor vi
// kan sætte at 'test' tilstand som primæret vil betyde at email og
// beskeder ikke sendes ud af system i test mode"). Samme lille formular-
// mønster som ScreeningRequestPolicySection nedenfor.
export function TestModeSection() {
  const t = useT();
  const [loadStatus, setLoadStatus] = useState("loading");
  const [testMode, setTestMode] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(null);

  function load() {
    setLoadStatus("loading");
    api
      .getTestModePolicy()
      .then((data) => {
        setTestMode(data.test_mode);
        setLoadStatus("ready");
      })
      .catch(() => setLoadStatus("error"));
  }

  useEffect(load, []);

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const updated = await api.updateTestModePolicy({ test_mode: testMode });
      setTestMode(updated.test_mode);
      setSaved(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="card settings-section">
      <h2>{t("testMode.heading")}</h2>
      <p className="muted">{t("testMode.description")}</p>

      {loadStatus === "loading" && <p className="muted">{t("common.loading")}</p>}
      {loadStatus === "error" && <div className="banner banner-error">{t("testMode.loadError")}</div>}

      {loadStatus === "ready" && (
        <form className="serial-config-form" onSubmit={submit}>
          <label className="serial-reuse-toggle">
            <input type="checkbox" checked={testMode} onChange={(e) => setTestMode(e.target.checked)} />
            {t("testMode.toggle")}
          </label>
          {testMode && <div className="banner banner-info">{t("testMode.activeHint")}</div>}

          {error && <div className="banner banner-error">{error}</div>}
          {saved && <div className="banner banner-info">{t("serial.saved")}</div>}

          <button type="submit" className="btn btn-primary" disabled={saving}>
            {t(saving ? "common.saving" : "common.save")}
          </button>
        </form>
      )}
    </div>
  );
}

export function ScreeningRequestPolicySection() {
  const t = useT();
  const [loadStatus, setLoadStatus] = useState("loading");
  const [requirePreferredAt, setRequirePreferredAt] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(null);

  function load() {
    setLoadStatus("loading");
    api
      .getScreeningRequestPolicy()
      .then((data) => {
        setRequirePreferredAt(data.require_preferred_at);
        setLoadStatus("ready");
      })
      .catch(() => setLoadStatus("error"));
  }

  useEffect(load, []);

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const updated = await api.updateScreeningRequestPolicy({
        require_preferred_at: requirePreferredAt,
      });
      setRequirePreferredAt(updated.require_preferred_at);
      setSaved(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="card settings-section">
      <h2>{t("screeningRequestPolicy.heading")}</h2>
      <p className="muted">{t("screeningRequestPolicy.description")}</p>

      {loadStatus === "loading" && <p className="muted">{t("common.loading")}</p>}
      {loadStatus === "error" && (
        <div className="banner banner-error">{t("screeningRequestPolicy.loadError")}</div>
      )}

      {loadStatus === "ready" && (
        <form className="serial-config-form" onSubmit={submit}>
          <label className="serial-reuse-toggle">
            <input
              type="checkbox"
              checked={requirePreferredAt}
              onChange={(e) => setRequirePreferredAt(e.target.checked)}
            />
            {t("screeningRequestPolicy.requirePreferredAt")}
          </label>

          {error && <div className="banner banner-error">{error}</div>}
          {saved && <div className="banner banner-info">{t("serial.saved")}</div>}

          <button type="submit" className="btn btn-primary" disabled={saving}>
            {t(saving ? "common.saving" : "common.save")}
          </button>
        </form>
      )}
    </div>
  );
}

export function PasswordPolicySection() {
  const t = useT();
  const [loadStatus, setLoadStatus] = useState("loading");
  const [minLength, setMinLength] = useState(8);
  const [requireUppercase, setRequireUppercase] = useState(false);
  const [requireLowercase, setRequireLowercase] = useState(false);
  const [requireDigit, setRequireDigit] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(null);

  function applyPolicy(data) {
    setMinLength(data.password_min_length);
    setRequireUppercase(data.password_require_uppercase);
    setRequireLowercase(data.password_require_lowercase);
    setRequireDigit(data.password_require_digit);
  }

  function load() {
    setLoadStatus("loading");
    api
      .getPasswordPolicy()
      .then((data) => {
        applyPolicy(data);
        setLoadStatus("ready");
      })
      .catch(() => setLoadStatus("error"));
  }

  useEffect(load, []);

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const updated = await api.updatePasswordPolicy({
        password_min_length: minLength,
        password_require_uppercase: requireUppercase,
        password_require_lowercase: requireLowercase,
        password_require_digit: requireDigit,
      });
      applyPolicy(updated);
      setSaved(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="card settings-section">
      <h2>{t("passwordPolicy.heading")}</h2>
      <p className="muted">{t("passwordPolicy.description")}</p>

      {loadStatus === "loading" && <p className="muted">{t("common.loading")}</p>}
      {loadStatus === "error" && (
        <div className="banner banner-error">{t("passwordPolicy.loadError")}</div>
      )}

      {loadStatus === "ready" && (
        <form className="serial-config-form" onSubmit={submit}>
          <label>
            {t("passwordPolicy.minLength")}
            <input
              type="number"
              min={6}
              max={64}
              value={minLength}
              onChange={(e) => setMinLength(Number(e.target.value))}
            />
          </label>
          <label className="serial-reuse-toggle">
            <input
              type="checkbox"
              checked={requireUppercase}
              onChange={(e) => setRequireUppercase(e.target.checked)}
            />
            {t("passwordPolicy.requireUppercase")}
          </label>
          <label className="serial-reuse-toggle">
            <input
              type="checkbox"
              checked={requireLowercase}
              onChange={(e) => setRequireLowercase(e.target.checked)}
            />
            {t("passwordPolicy.requireLowercase")}
          </label>
          <label className="serial-reuse-toggle">
            <input
              type="checkbox"
              checked={requireDigit}
              onChange={(e) => setRequireDigit(e.target.checked)}
            />
            {t("passwordPolicy.requireDigit")}
          </label>

          {error && <div className="banner banner-error">{error}</div>}
          {saved && <div className="banner banner-info">{t("serial.saved")}</div>}

          <button type="submit" className="btn btn-primary" disabled={saving}>
            {t(saving ? "common.saving" : "common.save")}
          </button>
        </form>
      )}
    </div>
  );
}

/**
 * Feature #183 (Jan: "lave en dianostik modul i portal under settings som
 * vi kan bruge til at få erfaring med ... skal vi have en funktion som
 * læser alle relavante sætting ud og det er input, vol,
 * audio_listening_mode, audio_input_format og en status live updatering på
 * update_callback"). Ren overvågning — sætter intet på AVM'en; det er
 * `anthem_service`/`api/anthem.py`'s job at skrive events, denne
 * komponent læser dem kun.
 *
 * Rå `fetch` + manuel linje-for-linje SSE-læsning i stedet for en almindelig
 * `EventSource` — se `api.openAnthemDiagnosticsStream`s kommentar for
 * hvorfor (kort: EventSource skjuler den specifikke 400/409-fejlbesked ved
 * en mislykket forbindelse, hvilket CLAUDE.md regel 16 kræver at vi viser).
 */
export function AnthemDiagnosticsSection() {
  const t = useT();
  const [streamStatus, setStreamStatus] = useState("idle"); // idle | connecting | live | error
  const [errorMessage, setErrorMessage] = useState(null);
  const [currentState, setCurrentState] = useState(null);
  const [events, setEvents] = useState([]);
  const [recording, setRecording] = useState(false);
  const [recordedCount, setRecordedCount] = useState(0);

  const abortControllerRef = useRef(null);
  const recordingRef = useRef(false);
  const recordedEventsRef = useRef([]);

  // Loft på den viste log — en session der kører i timevis (fx hele en
  // filmaften) må ikke stille og roligt vokse DOM'en/hukommelsen ubegrænset.
  // Selve OPTAGELSEN (recordedEventsRef) beholder alt — det er den man
  // downloader og skal bruge bagefter, kun den løbende visning beskæres.
  const MAX_DISPLAYED_EVENTS = 300;

  function pushEvent(event) {
    setEvents((prev) => {
      const next = [...prev, event];
      return next.length > MAX_DISPLAYED_EVENTS ? next.slice(-MAX_DISPLAYED_EVENTS) : next;
    });
    if (recordingRef.current) {
      recordedEventsRef.current.push(event);
      setRecordedCount(recordedEventsRef.current.length);
    }
  }

  async function start() {
    setStreamStatus("connecting");
    setErrorMessage(null);
    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const response = await api.openAnthemDiagnosticsStream(controller.signal);
      if (!response.ok) {
        // Intet JSON i fejlsvaret → den generiske tekst nedenfor overtager.
        const body = await response.json().catch(() => null);
        setErrorMessage(body?.detail ?? t("anthemDiag.genericError"));
        setStreamStatus("error");
        return;
      }

      setStreamStatus("live");
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const chunks = buffer.split("\n\n");
        buffer = chunks.pop() ?? "";
        for (const chunk of chunks) {
          if (!chunk.startsWith("data: ")) continue; // heartbeat-kommentarlinjer springes over
          const event = JSON.parse(chunk.slice(6));
          if (event.type === "error") {
            setErrorMessage(event.message);
            setStreamStatus("error");
          } else {
            setCurrentState(event);
          }
          pushEvent(event);
        }
      }
      // Strømmen sluttede uden en eksplicit fejl (fx serveren lukkede den) —
      // vis den ikke fortsat som "live".
      setStreamStatus((current) => (current === "live" ? "idle" : current));
    } catch (err) {
      if (err.name === "AbortError") return; // brugeren trykkede selv Stop
      setErrorMessage(err.message);
      setStreamStatus("error");
    }
  }

  function stop() {
    abortControllerRef.current?.abort();
    setStreamStatus("idle");
  }

  function toggleRecording() {
    if (recordingRef.current) {
      recordingRef.current = false;
      setRecording(false);
      return;
    }
    recordedEventsRef.current = [];
    setRecordedCount(0);
    recordingRef.current = true;
    setRecording(true);
  }

  function download() {
    const blob = new Blob([JSON.stringify(recordedEventsRef.current, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `anthem-diagnostik-${new Date().toISOString().replace(/[:.]/g, "-")}.json`;
    link.click();
    URL.revokeObjectURL(url);
  }

  useEffect(() => {
    return () => abortControllerRef.current?.abort();
  }, []);

  const live = streamStatus === "live";

  return (
    <div className="card settings-section">
      <h2>{t("anthemDiag.heading")}</h2>
      <p className="muted">{t("anthemDiag.description")}</p>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
        <button
          type="button"
          className="btn btn-primary"
          onClick={live ? stop : start}
          disabled={streamStatus === "connecting"}
        >
          {t(
            streamStatus === "connecting"
              ? "anthemDiag.connecting"
              : live
                ? "anthemDiag.stop"
                : "anthemDiag.start"
          )}
        </button>
        <button type="button" className="btn" onClick={toggleRecording} disabled={!live}>
          {t(recording ? "anthemDiag.stopRecording" : "anthemDiag.startRecording")}
        </button>
        {recordedCount > 0 && (
          <button type="button" className="btn" onClick={download}>
            {t("anthemDiag.download", { count: recordedCount })}
          </button>
        )}
      </div>

      {streamStatus === "error" && errorMessage && (
        <div className="banner banner-error" style={{ marginBottom: 12 }}>
          {errorMessage}
        </div>
      )}

      {currentState && (
        <div className="plex-diagnostics">
          <dl className="plex-diag-grid">
            <dt>{t("anthemDiag.fieldPower")}</dt>
            <dd>{t(currentState.power ? "anthemDiag.on" : "anthemDiag.off")}</dd>
            <dt>{t("anthemDiag.fieldInput")}</dt>
            <dd>
              {currentState.input_name} ({currentState.input_number})
            </dd>
            <dt>{t("anthemDiag.fieldVolume")}</dt>
            <dd>{currentState.volume}</dd>
            <dt>{t("anthemDiag.fieldMute")}</dt>
            <dd>{t(currentState.mute ? "anthemDiag.on" : "anthemDiag.off")}</dd>
            <dt>{t("anthemDiag.fieldAudioMode")}</dt>
            <dd>{currentState.audio_listening_mode_text}</dd>
            <dt>{t("anthemDiag.fieldAudioFormat")}</dt>
            <dd>{currentState.audio_input_format_text}</dd>
            <dt>{t("anthemDiag.fieldAudioChannels")}</dt>
            <dd>{currentState.audio_input_channels_text}</dd>
          </dl>
        </div>
      )}

      <h3 style={{ fontSize: "0.95rem", margin: "16px 0 4px" }}>{t("anthemDiag.eventLogHeading")}</h3>
      {events.length === 0 ? (
        <p className="muted">{t("anthemDiag.noEvents")}</p>
      ) : (
        <ul className="anthem-log">
          {events
            .slice()
            .reverse()
            .map((event, i) => (
              <li key={i}>
                <span className="anthem-log-time">
                  {new Date(event.timestamp).toLocaleTimeString()}
                </span>{" "}
                <span className="anthem-log-type">{event.type}</span>{" "}
                {event.raw && <span className="anthem-log-raw">{event.raw}</span>}
                {event.type === "error" && event.message}
              </li>
            ))}
        </ul>
      )}
    </div>
  );
}
