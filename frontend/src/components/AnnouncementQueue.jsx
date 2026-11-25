import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { useLocale, useT } from "../i18n";
import { ANNOUNCEMENTS_CHANGED_EVENT, announceQueueChanged } from "../utils/announcements";
import { posterSrc } from "../utils/posterUrl";
import "./AnnouncementQueue.css";

/**
 * Feature #228 — "Samlet opdatering" i Indstillinger → Beskeder: den fælles
 * kø af nye titler, og knappen der sender dem alle som ÉN besked til alle
 * brugere. Admin + standard (backend håndhæver `require_not_guest`).
 */
export default function AnnouncementQueueSection() {
  const t = useT();
  const locale = useLocale();
  const [items, setItems] = useState([]);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);
  const [sentCount, setSentCount] = useState(null);
  // Feature #232 — forhåndsvisning af den rigtige mail (null = lukket).
  const [preview, setPreview] = useState(null);

  const load = useCallback(async () => {
    try {
      setItems(await api.listAnnouncements());
      setLoaded(true);
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function togglePreview() {
    if (preview) {
      setPreview(null);
      return;
    }
    setBusy("preview");
    setError(null);
    try {
      setPreview(await api.previewAnnouncements());
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(null);
    }
  }

  async function remove(item) {
    setBusy(item.id);
    setError(null);
    setSentCount(null);
    // Previewet viste den gamle kø — luk det hellere end at vise noget forkert.
    setPreview(null);
    try {
      await api.removeAnnouncement(item.id);
      setItems((prev) => prev.filter((i) => i.id !== item.id));
    } catch (err) {
      setError(err.message);
      // Fx allerede sendt af en anden — vis køen som den faktisk er nu.
      await load();
    } finally {
      setBusy(null);
      announceQueueChanged();
    }
  }

  async function sendAll() {
    if (!window.confirm(t("announcements.confirmSend", { count: items.length }))) return;
    setBusy("send");
    setError(null);
    setSentCount(null);
    setPreview(null);
    try {
      const result = await api.sendAnnouncements();
      setSentCount(result.sent_count);
    } catch (err) {
      // Fx test-tilstand eller en tom kø — køen står urørt i backend.
      setError(err.message);
    } finally {
      setBusy(null);
      await load();
      announceQueueChanged();
    }
  }

  return (
    <div className="card settings-section">
      <h2>{t("announcements.heading")}</h2>
      <p className="muted">{t("announcements.description")}</p>

      {error && <div className="banner banner-error">{error}</div>}
      {sentCount !== null && (
        <div className="banner banner-info">{t("announcements.sent", { count: sentCount })}</div>
      )}

      {loaded && items.length === 0 && <p className="muted">{t("announcements.empty")}</p>}

      {items.length > 0 && (
        <>
          <ul className="announce-queue">
            {items.map((item) => (
              <li key={item.id} className="announce-queue-row">
                {item.poster_url ? (
                  <img
                    className="announce-queue-poster"
                    src={posterSrc(item.poster_url, "w185")}
                    alt=""
                    loading="lazy"
                  />
                ) : (
                  <span className="announce-queue-poster announce-queue-poster--empty" aria-hidden="true" />
                )}
                <span className="announce-queue-text">
                  <strong>
                    {item.title}
                    {item.year != null && <span className="announce-queue-year"> ({item.year})</span>}
                  </strong>
                  <span className="muted">
                    {t(item.media_kind === "tv" ? "announcements.kindTv" : "announcements.kindMovie")}
                    {" · "}
                    {t("announcements.addedBy", {
                      name: item.added_by,
                      date: new Date(item.created_at).toLocaleDateString(locale),
                    })}
                  </span>
                </span>
                <button
                  type="button"
                  className="btn"
                  onClick={() => remove(item)}
                  disabled={busy !== null}
                  aria-label={t("announcements.removeAria", { title: item.title })}
                >
                  {t("announcements.remove")}
                </button>
              </li>
            ))}
          </ul>
          <div className="announce-queue-actions">
            <button
              type="button"
              className="btn"
              onClick={togglePreview}
              disabled={busy !== null}
              aria-expanded={preview !== null}
            >
              {busy === "preview"
                ? t("announcements.previewLoading")
                : t(preview ? "announcements.previewHide" : "announcements.preview")}
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={sendAll}
              disabled={busy !== null}
            >
              {busy === "send"
                ? t("announcements.sending")
                : t("announcements.send", { count: items.length })}
            </button>
          </div>
          {preview && (
            <div className="announce-preview">
              <div className="announce-preview-subject">
                <span className="muted">{t("announcements.previewSubject")}</span> <strong>{preview.subject}</strong>
              </div>
              <iframe
                title={t("announcements.previewFrameTitle")}
                srcDoc={preview.html}
                className="announce-preview-frame"
                sandbox=""
              />
            </div>
          )}
        </>
      )}
    </div>
  );
}

/**
 * Feature #228 — diskret påmindelse øverst på Film- og TV-siden, når køen
 * ikke er tom. Kun for admin/standard (App renderer den ikke for gæster).
 */
export function AnnouncementReminder({ onOpen }) {
  const t = useT();
  const [count, setCount] = useState(0);

  const refresh = useCallback(() => {
    api
      .listAnnouncements()
      .then((rows) => setCount(rows.length))
      // Påmindelsen er en bekvemmelighed; fejler hentningen, vises den bare
      // ikke. Selve køen i Indstillinger viser fejlen, hvis man åbner den.
      .catch(() => setCount(0));
  }, []);

  useEffect(() => {
    refresh();
    window.addEventListener(ANNOUNCEMENTS_CHANGED_EVENT, refresh);
    return () => window.removeEventListener(ANNOUNCEMENTS_CHANGED_EVENT, refresh);
  }, [refresh]);

  if (count === 0) return null;
  return (
    <div className="announce-reminder" role="status">
      <span>{t("announcements.reminder", { count })}</span>
      <button type="button" className="btn" onClick={onOpen}>
        {t("announcements.reminderOpen")}
      </button>
    </div>
  );
}
