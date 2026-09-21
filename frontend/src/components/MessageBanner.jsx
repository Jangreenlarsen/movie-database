import { useEffect, useRef, useState } from "react";

import { api } from "../api/client";
import { useLocale, useT } from "../i18n";
import "./MessageBanner.css";

// Feature #135 — hvor ofte indbakken polles, så en besked sendt til en
// allerede-indlogget bruger dukker op af sig selv. 20 s er rigeligt til en
// hjemme-app; overstyrbart via prop i test.
const POLL_INTERVAL_MS = 20000;

// Feature #226 (Jan: "hvis en bruger ikke har være login i lang tid så kan
// det være at han har 1000 beskeder kondesere dem til max 3 besked") — et
// langt fravær kan ophobe et efterslæb der ellers ville fylde hele skærmen
// med bannere. 3 er nok til at vise noget konkret uden at overvælde.
const MAX_VISIBLE_MESSAGES = 3;

/**
 * Feature #100 — beskeder fra en admin, vist som bannere øverst i appen
 * indtil modtageren lukker dem (Jans valg 2026-08-09).
 *
 * Bannere frem for en klokke med ulæst-tæller: en besked her er typisk
 * "husk visning på fredag", og skal være svær at overse. Prisen er at en
 * lukket besked er væk — der er ingen historik at finde den frem i, hvilket
 * er en bevidst afvejning og ikke en mangel.
 *
 * Lukningen markerer beskeden læst i backenden, så afsenderen kan se hvem
 * der har set den. Fejler det kald, bliver banneret stående frem for at
 * forsvinde lokalt — ellers ville brugeren tro han havde kvitteret, mens
 * afsenderen stadig så beskeden som ulæst.
 *
 * Feature #226 — er der mere end `MAX_VISIBLE_MESSAGES` ulæst (et langt
 * fravær kan sagtens ophobe hundredvis), vises kun de nyeste + en fælles
 * notits om det samlede antal og et link til "Dine beskeder" i
 * Indstillinger → Beskeder, hvor hele efterslæbet kan ses og ryddes på én
 * gang i stedet for at skulle lukkes ét banner ad gangen.
 */
export default function MessageBanner({ pollIntervalMs = POLL_INTERVAL_MS, onGoToSettings }) {
  const t = useT();
  const locale = useLocale();
  const [messages, setMessages] = useState([]);
  const [dismissing, setDismissing] = useState(null);
  const [error, setError] = useState(null);
  // Feature #135 — beskeder brugeren har lukket lokalt. En poll må aldrig
  // hente dem tilbage på skærmen, hvis den når indbakken før `markMessageRead`
  // er registreret i backenden (race).
  const dismissedRef = useRef(new Set());

  useEffect(() => {
    let active = true;
    const load = () =>
      api
        .getInbox()
        .then((fresh) => {
          if (!active) return;
          // Tilføj kun *nye* beskeder — fjern aldrig en åben besked her, så
          // den ikke blinker eller genopstår mellem polls.
          setMessages((prev) => {
            const known = new Set(prev.map((m) => m.id));
            const additions = fresh.filter(
              (m) => !known.has(m.id) && !dismissedRef.current.has(m.id)
            );
            return additions.length ? [...prev, ...additions] : prev;
          });
        })
        // Ingen synlig fejl her: en utilgængelig indbakke må ikke lægge sig
        // oven på hele appen. Er der en besked, kommer den ved næste poll.
        .catch(() => {});

    load();
    // Feature #135 — poll så en besked sendt til en allerede-indlogget bruger
    // dukker op af sig selv, uden at skulle genindlæse/logge ind igen.
    const timer = setInterval(load, pollIntervalMs);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [pollIntervalMs]);

  function dismiss(messageId) {
    setDismissing(messageId);
    setError(null);
    api
      .markMessageRead(messageId)
      .then(() => {
        dismissedRef.current.add(messageId);
        setMessages((prev) => prev.filter((m) => m.id !== messageId));
      })
      .catch((err) => setError(err.message))
      .finally(() => setDismissing(null));
  }

  if (messages.length === 0) return null;

  // Feature #226 — de NYESTE er de mest relevante at vise når der er for
  // mange til at rumme dem alle; resten venter uændret i indbakken og kan
  // ses/ryddes samlet i Indstillinger → Beskeder.
  const overflowing = messages.length > MAX_VISIBLE_MESSAGES;
  const visibleMessages = overflowing ? messages.slice(-MAX_VISIBLE_MESSAGES) : messages;

  return (
    <div className="message-banners">
      {overflowing && (
        <div className="message-banner message-banner-overflow">
          <div className="message-banner-body">
            <p className="message-banner-text">
              {t("messages.overflowNotice", { count: messages.length, shown: MAX_VISIBLE_MESSAGES })}
            </p>
          </div>
          {onGoToSettings && (
            <button type="button" className="btn" onClick={onGoToSettings}>
              {t("messages.overflowGoToSettings")}
            </button>
          )}
        </div>
      )}
      {visibleMessages.map((message) => (
        <div key={message.id} className="message-banner">
          <div className="message-banner-body">
            <div className="message-banner-subject">{message.subject}</div>
            <p className="message-banner-text">{message.body}</p>
            <div className="message-banner-meta">
              {t("messages.from", {
                sender: message.sent_by,
                date: new Date(message.created_at).toLocaleDateString(locale),
              })}
            </div>
          </div>
          <button
            type="button"
            className="btn"
            onClick={() => dismiss(message.id)}
            disabled={dismissing === message.id}
          >
            {t(dismissing === message.id ? "messages.dismissing" : "messages.dismiss")}
          </button>
        </div>
      ))}
      {error && <div className="banner banner-error">{t("messages.dismissError", { message: error })}</div>}
    </div>
  );
}
