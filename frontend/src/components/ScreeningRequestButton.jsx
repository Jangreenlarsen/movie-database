import { useEffect, useState } from "react";
import { api } from "../api/client";
import DateTime24Input from "./DateTime24Input";
import { formatShortDate, formatTime } from "../utils/cinemaFormat";
import { useLocale, useT } from "../i18n";
import "./ScreeningRequestButton.css";

/**
 * "Ønsk visning i Voldby BIO" button (feature #62) — shared by the movie
 * and TV-show detail modals. Checks on mount whether the current user has
 * already requested this title, so re-opening the modal shows the correct
 * state instead of always starting from scratch.
 *
 * Feature #85: the button no longer sends immediately. It opens a small box
 * where the requester can add a free-text message and suggest a time. Once
 * sent, the button shows back what you wrote, since a request can't be
 * edited afterwards (the backend keeps your first entry; see
 * screening_request_repository.add_requester).
 *
 * Feature #176 (Jan: "når en guest eller standart user ønske en forvisning
 * i bio skal man afkraves at man også deffinere en dato og tidspunkt") —
 * the message stays optional, but a preferred date/time is now mandatory:
 * "Send ønske" stays disabled until one is picked, mirroring the backend's
 * own (authoritative) requirement on `ScreeningRequestCreate.preferred_at`.
 *
 * Feature #177 (Jan: "vi skal kunne sætte om guest ... skal bruge dato/tid
 * eller ikke") — that requirement is now admin-configurable, but ONLY for
 * the guest role; standard/admin stay unconditionally required. Defaults to
 * "required" while the policy is still loading, matching the backend's own
 * default and avoiding a flash of an enabled button that then disables.
 */
export default function ScreeningRequestButton({ mediaKind, id, username, role }) {
  const t = useT();
  const locale = useLocale();
  const [status, setStatus] = useState("idle"); // idle | composing | requesting | requested | error
  const [error, setError] = useState(null);
  const [message, setMessage] = useState("");
  const [preferredAt, setPreferredAt] = useState("");
  // Hvad DENNE bruger tidligere har ønsket for titlen — vises igen ved
  // genåbning af vinduet, så et ønske ikke bare bliver til et anonymt flueben.
  const [myRequest, setMyRequest] = useState(null);
  // Feature #177 — kun relevant for gæster; standard/admin er altid true.
  const [requireForGuests, setRequireForGuests] = useState(true);
  const preferredAtRequired = role !== "guest" || requireForGuests;

  // `requested_by` rummer alle der har ønsket titlen — vores egen entry
  // findes på brugernavn, så vi aldrig kommer til at vise en andens besked.
  function ownEntry(request) {
    return request?.requested_by?.find((r) => r.username === username) ?? null;
  }

  useEffect(() => {
    const key = mediaKind === "movie" ? "movie_id" : "tv_show_id";
    api
      .myScreeningRequests()
      .then((requests) => {
        const mine = requests.find((r) => r[key] === id);
        if (!mine) return;
        setStatus("requested");
        setMyRequest(ownEntry(mine));
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mediaKind, id, username]);

  useEffect(() => {
    if (role !== "guest") return;
    api
      .getScreeningRequestPolicy()
      .then((policy) => setRequireForGuests(policy.require_preferred_at_for_guests))
      .catch(() => {});
  }, [role]);

  async function submitRequest() {
    setStatus("requesting");
    setError(null);
    try {
      const created = await api.requestScreening(mediaKind, id, { message, preferredAt });
      setStatus("requested");
      setMyRequest(ownEntry(created));
    } catch (err) {
      setError(err.message);
      setStatus("composing");
    }
  }

  function closeComposer() {
    setStatus("idle");
    setError(null);
  }

  if (status === "requested") {
    return (
      <div className="screening-request">
        <button type="button" className="btn" disabled>
          {t("request.requested")}
        </button>
        {(myRequest?.message || myRequest?.preferred_at) && (
          <div className="screening-request-mine muted">
            {myRequest.message && <>„{myRequest.message}“</>}
            {myRequest.preferred_at && (
              <>
                {myRequest.message ? " · " : ""}
                {t("request.at", {
                  date: formatShortDate(myRequest.preferred_at, locale),
                  time: formatTime(myRequest.preferred_at, locale),
                })}
              </>
            )}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="screening-request">
      <button type="button" className="btn" onClick={() => setStatus("composing")}>
        {t("request.button")}
      </button>

      {(status === "composing" || status === "requesting") && (
        // Egen modal oven på film-/serie-vinduet: modal-footer er en smal
        // knap-række uden plads til en formular. stopPropagation er
        // nødvendig, fordi et klik ellers bobler op til det underliggende
        // vindues backdrop og lukker hele detaljevinduet.
        <div
          className="modal-backdrop"
          onClick={(e) => {
            e.stopPropagation();
            closeComposer();
          }}
        >
          <div className="modal-card screening-request-card" onClick={(e) => e.stopPropagation()}>
            <div className="screening-request-body">
              <h3>{t("request.button")}</h3>
              <p className="muted">{t(preferredAtRequired ? "request.hint" : "request.hintOptional")}</p>

              <label className="modal-section-label" htmlFor="screening-request-message">
                {t("request.messageLabel")}
              </label>
              <textarea
                id="screening-request-message"
                rows={3}
                maxLength={500}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder={t("request.messagePlaceholder")}
              />

              <label className="modal-section-label" style={{ marginTop: 12 }}>
                {t(preferredAtRequired ? "request.preferredLabel" : "request.preferredLabelOptional")}
              </label>
              <DateTime24Input value={preferredAt} onChange={setPreferredAt} />

              {error && (
                <div className="banner banner-error" style={{ marginTop: 12 }}>
                  {error}
                </div>
              )}
            </div>

            <div className="modal-footer">
              <button
                type="button"
                className="btn"
                onClick={closeComposer}
                disabled={status === "requesting"}
              >
                {t("common.cancel")}
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={submitRequest}
                disabled={status === "requesting" || (preferredAtRequired && !preferredAt)}
              >
                {t(status === "requesting" ? "request.sending" : "request.send")}
              </button>
            </div>
          </div>
        </div>
      )}

      {error && status === "idle" && (
        <div className="banner banner-error" style={{ marginTop: 8 }}>
          {error}
        </div>
      )}
    </div>
  );
}
