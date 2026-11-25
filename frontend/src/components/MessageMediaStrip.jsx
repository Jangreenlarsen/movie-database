import { useT } from "../i18n";
import { posterSrc } from "../utils/posterUrl";
import "./MessageMediaStrip.css";

// Feature #232 — en lang samlet opdatering må ikke fylde hele banneret.
export const MAX_STRIP_ITEMS = 8;

/**
 * Feature #232 — plakaterne for de titler en besked handler om (samlet
 * opdatering / ny i samlingen). Vises over brødteksten i banneret og under
 * "Dine beskeder". Tom eller manglende `media` (alle andre beskeder) giver
 * ingenting.
 */
export default function MessageMediaStrip({ media, max = MAX_STRIP_ITEMS }) {
  const t = useT();
  if (!media || media.length === 0) return null;
  const shown = media.slice(0, max);
  const hidden = media.length - shown.length;
  return (
    <ul className="message-media-strip" aria-label={t("messages.mediaStripLabel", { count: media.length })}>
      {shown.map((item, index) => (
        <li
          key={`${item.media_kind}-${item.title}-${index}`}
          className={`message-media-item message-media-item--${item.media_kind === "tv" ? "tv" : "movie"}`}
          title={item.year != null ? `${item.title} (${item.year})` : item.title}
        >
          {item.poster_url ? (
            <img src={posterSrc(item.poster_url, "w185")} alt={item.title} loading="lazy" />
          ) : (
            <span className="message-media-fallback">{item.title}</span>
          )}
        </li>
      ))}
      {hidden > 0 && (
        <li className="message-media-item message-media-more">
          {t("messages.mediaStripMore", { count: hidden })}
        </li>
      )}
    </ul>
  );
}
