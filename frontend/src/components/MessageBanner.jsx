import { useEffect, useState } from "react";

import { api } from "../api/client";
import { useLocale, useT } from "../i18n";
import "./MessageBanner.css";

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
 */
export default function MessageBanner() {
  const t = useT();
  const locale = useLocale();
  const [messages, setMessages] = useState([]);
  const [dismissing, setDismissing] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api
      .getInbox()
      .then(setMessages)
      // Ingen synlig fejl her: en utilgængelig indbakke må ikke lægge sig
      // oven på hele appen. Er der en besked, kommer den ved næste
      // sideindlæsning.
      .catch(() => {});
  }, []);

  function dismiss(messageId) {
    setDismissing(messageId);
    setError(null);
    api
      .markMessageRead(messageId)
      .then(() => setMessages((prev) => prev.filter((m) => m.id !== messageId)))
      .catch((err) => setError(err.message))
      .finally(() => setDismissing(null));
  }

  if (messages.length === 0) return null;

  return (
    <div className="message-banners">
      {messages.map((message) => (
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
