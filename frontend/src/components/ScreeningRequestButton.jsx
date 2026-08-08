import { useEffect, useState } from "react";
import { api } from "../api/client";
import DateTime24Input from "./DateTime24Input";
import { formatShortDate, formatTime } from "../utils/cinemaFormat";
import "./ScreeningRequestButton.css";

/**
 * "Ønsk visning i Voldby BIO" button (feature #62) — shared by the movie
 * and TV-show detail modals. Checks on mount whether the current user has
 * already requested this title, so re-opening the modal shows the correct
 * state instead of always starting from scratch.
 *
 * Feature #85: the button no longer sends immediately. It opens a small box
 * where the requester can add a free-text message and/or suggest a time —
 * both optional, so "åbn, tryk Send ønske" is still the one-decision path
 * it used to be. Once sent, the button shows back what you wrote, since a
 * request can't be edited afterwards (the backend keeps your first entry;
 * see screening_request_repository.add_requester).
 */
export default function ScreeningRequestButton({ mediaKind, id, username }) {
  const [status, setStatus] = useState("idle"); // idle | composing | requesting | requested | error
  const [error, setError] = useState(null);
  const [message, setMessage] = useState("");
  const [preferredAt, setPreferredAt] = useState("");
  // Hvad DENNE bruger tidligere har ønsket for titlen — vises igen ved
  // genåbning af vinduet, så et ønske ikke bare bliver til et anonymt flueben.
  const [myRequest, setMyRequest] = useState(null);

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
          ✓ Ønsket til Voldby BIO
        </button>
        {(myRequest?.message || myRequest?.preferred_at) && (
          <div className="screening-request-mine muted">
            {myRequest.message && <>„{myRequest.message}“</>}
            {myRequest.preferred_at && (
              <>
                {myRequest.message ? " · " : ""}⏰ {formatShortDate(myRequest.preferred_at)} kl.{" "}
                {formatTime(myRequest.preferred_at)}
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
        🎬 Ønsk visning i Voldby BIO
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
              <h3>🎬 Ønsk visning i Voldby BIO</h3>
              <p className="muted">
                Skriv gerne hvornår du kunne tænke dig den vist — begge felter er valgfri.
              </p>

              <label className="modal-section-label" htmlFor="screening-request-message">
                Besked (valgfri)
              </label>
              <textarea
                id="screening-request-message"
                rows={3}
                maxLength={500}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Fx: Gerne en fredag aften — så laver jeg popcorn!"
              />

              <label className="modal-section-label" style={{ marginTop: 12 }}>
                Ønsket tidspunkt (valgfri)
              </label>
              <DateTime24Input value={preferredAt} onChange={setPreferredAt} />
              {preferredAt && (
                <button
                  type="button"
                  className="btn screening-request-clear"
                  onClick={() => setPreferredAt("")}
                >
                  Ryd tidspunkt
                </button>
              )}

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
                Annullér
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={submitRequest}
                disabled={status === "requesting"}
              >
                {status === "requesting" ? "Sender..." : "Send ønske"}
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
