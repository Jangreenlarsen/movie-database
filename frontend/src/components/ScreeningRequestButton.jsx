import { useEffect, useState } from "react";
import { api } from "../api/client";

/**
 * "Ønsk visning i Voldby BIO" button (feature #62) — shared by the movie
 * and TV-show detail modals. Checks on mount whether the current user has
 * already requested this title, so re-opening the modal shows the correct
 * state instead of always starting from scratch.
 */
export default function ScreeningRequestButton({ mediaKind, id }) {
  const [status, setStatus] = useState("idle"); // idle | requesting | requested | error
  const [error, setError] = useState(null);

  useEffect(() => {
    const key = mediaKind === "movie" ? "movie_id" : "tv_show_id";
    api
      .myScreeningRequests()
      .then((requests) => {
        if (requests.some((r) => r[key] === id)) setStatus("requested");
      })
      .catch(() => {});
  }, [mediaKind, id]);

  async function requestScreening() {
    setStatus("requesting");
    setError(null);
    try {
      await api.requestScreening(mediaKind, id);
      setStatus("requested");
    } catch (err) {
      setError(err.message);
      setStatus("idle");
    }
  }

  return (
    <div style={{ display: "inline-block" }}>
      <button
        type="button"
        className="btn"
        onClick={requestScreening}
        disabled={status === "requesting" || status === "requested"}
      >
        {status === "requested"
          ? "✓ Ønsket til Voldby BIO"
          : status === "requesting"
            ? "Sender..."
            : "🎬 Ønsk visning i Voldby BIO"}
      </button>
      {error && (
        <div className="banner banner-error" style={{ marginTop: 8 }}>
          {error}
        </div>
      )}
    </div>
  );
}
