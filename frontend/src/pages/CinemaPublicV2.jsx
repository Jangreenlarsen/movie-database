import { useEffect, useState } from "react";
import { api } from "../api/client";
import { formatShortDate, formatTime } from "../utils/cinemaFormat";
import LanguagePicker from "../components/LanguagePicker";
import { useLocale, useT } from "../i18n";
import {
  GalleryModal,
  GuestLoginBanner,
  PressModal,
  PublicLoginPanel,
  PublicLoginToggle,
  PublicScreeningCard,
  RefreshmentsModal,
} from "./CinemaPublic";
// Genbruger modalernes/kortenes eksisterende CSS uændret (se
// CinemaPublicV2.jsx's importer af CinemaPublic — kun den visuelle skal
// herunder er ny).
import "./CinemaPublic.css";
import "./Cinema.css";
import "./Login.css";
import "./CinemaPublicV2.css";

// Feature #191 — "Voldby BIO v2": ny visuel forside på /bio2, sideordnet med
// den eksisterende /bio (CinemaPublic.jsx), som forbliver fuldstændig
// uændret og er den side der bruges i produktion i dag. /bio2 er bevidst en
// selvstændig komponent frem for en ombygning af CinemaPublic.jsx — kun den
// visuelle skal (papir-baggrund, frilagt logo, foto-kollage, filmstrimmel)
// er ny; al forretningslogik (login/opret, presse/forplejning/galleri,
// visningsliste) er genbrugt via de navngivne eksporter CinemaPublic.jsx nu
// også tilbyder.
export default function CinemaPublicV2({ user = null, language, onLanguageChange }) {
  const t = useT();
  const locale = useLocale();
  const [loginOpen, setLoginOpen] = useState(false);
  const [galleryOpen, setGalleryOpen] = useState(false);
  const [pressOpen, setPressOpen] = useState(false);
  const [refreshmentsOpen, setRefreshmentsOpen] = useState(false);
  const [screenings, setScreenings] = useState([]);
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    api
      .listScreenings(true)
      .then((data) => {
        setScreenings(data);
        setStatus("ready");
      })
      .catch(() => setStatus("error"));
  }, []);

  useEffect(() => {
    // Bevidst tavs: besøgstælling er statistik, ikke noget den besøgende skal mærke.
    api.recordVisit({ page: "bio2" }).catch(() => {});
  }, []);

  const nextScreening = screenings.length > 0 ? screenings[0] : null;

  return (
    <div className="cinema-v2-page">
      <img
        className="cinema-v2-filmstrip"
        src="/cinema/bio2-filmstrip.png"
        alt=""
        aria-hidden="true"
      />

      <header className="cinema-v2-hero">
        <div className="cinema-v2-hero-actions">
          <PublicLoginToggle user={user} open={loginOpen} onToggle={() => setLoginOpen((v) => !v)} />
          {onLanguageChange && (
            <LanguagePicker language={language} onChange={onLanguageChange} />
          )}
        </div>

        <h1 className="cinema-v2-sign">
          <img src="/cinema/bio2-sign-cutout.png" alt={t("public.signAlt")} />
        </h1>
        <p className="cinema-v2-tagline">{t("public.tagline")}</p>

        <div className="cinema-v2-collage">
          <img
            className="cinema-v2-collage-photo cinema-v2-collage-left"
            src="/cinema/voldbyBIO-3.jpg"
            alt={t("showcase.photo2Alt")}
          />
          <img
            className="cinema-v2-collage-photo cinema-v2-collage-right"
            src="/cinema/voldbyBIO-2-back.jpg"
            alt={t("showcase.photo3Alt")}
          />
          <img
            className="cinema-v2-collage-photo cinema-v2-collage-center"
            src="/cinema/voldbyBIO-1-front.jpg"
            alt={t("showcase.photo1Alt")}
          />
          {nextScreening && (
            <div className="cinema-v2-now-badge">
              <div className="cinema-v2-now-label">{t("public.upNextLabel")}</div>
              <div className="cinema-v2-now-title">
                {nextScreening.title ?? t("cinema.unknownTitle")} ·{" "}
                {formatShortDate(nextScreening.scheduled_at, locale)}{" "}
                {formatTime(nextScreening.scheduled_at, locale)}
              </div>
            </div>
          )}
        </div>
      </header>

      <main className="cinema-v2-main">
        <section className="cinema-v2-section">
          <div className="cinema-v2-section-heading-row">
            <h2 className="cinema-v2-section-heading">{t("public.about")}</h2>
            <div className="cinema-v2-section-actions">
              <button type="button" className="cinema-v2-ghost-btn" onClick={() => setPressOpen(true)}>
                📰 {t("public.pressNews")}
              </button>
              <button
                type="button"
                className="cinema-v2-ghost-btn"
                onClick={() => setRefreshmentsOpen(true)}
              >
                🍿 {t("public.refreshments")}
              </button>
              <button type="button" className="cinema-v2-ghost-btn" onClick={() => setGalleryOpen(true)}>
                🖼️ {t("public.gallery")}
              </button>
            </div>
          </div>

          <div className="cinema-v2-about-grid">
            <div className="cinema-v2-about-card cinema-v2-about-card--brick">
              <div className="cinema-v2-about-label">{t("showcase.roomHeading")}</div>
              <p>{t("showcase.roomText")}</p>
            </div>
            <div className="cinema-v2-about-card cinema-v2-about-card--amber">
              <div className="cinema-v2-about-label">{t("showcase.pictureHeading")}</div>
              <p>{t("showcase.pictureText")}</p>
            </div>
            <div className="cinema-v2-about-card cinema-v2-about-card--brick">
              <div className="cinema-v2-about-label">{t("showcase.soundHeading")}</div>
              <p>{t("showcase.soundText")}</p>
              <ul>
                <li>{t("showcase.amp1")}</li>
                <li>{t("showcase.amp2")}</li>
                <li>{t("showcase.amp3")}</li>
                <li>{t("showcase.amp4")}</li>
              </ul>
            </div>
          </div>
        </section>

        <section className="cinema-v2-section">
          <h2 className="cinema-v2-section-heading">{t("public.nowShowing")}</h2>
          {status === "loading" && <p className="muted">{t("cinema.loadingProgram")}</p>}
          {status === "error" && (
            <div className="banner banner-error">{t("cinema.programLoadError")}</div>
          )}
          {status === "ready" && screenings.length === 0 && (
            <p className="muted">{t("cinema.noScreenings")}</p>
          )}

          {screenings.length > 0 && (
            <div className="cinema-cards">
              {screenings.map((screening) => (
                <PublicScreeningCard key={screening.id} screening={screening} />
              ))}
            </div>
          )}
        </section>
      </main>

      {loginOpen && !user && (
        <PublicLoginPanel language={language} onClose={() => setLoginOpen(false)} />
      )}

      {galleryOpen && <GalleryModal onClose={() => setGalleryOpen(false)} />}

      {pressOpen && <PressModal onClose={() => setPressOpen(false)} />}

      {refreshmentsOpen && <RefreshmentsModal onClose={() => setRefreshmentsOpen(false)} />}

      {!user && <GuestLoginBanner onOpenLogin={() => setLoginOpen(true)} />}
    </div>
  );
}
