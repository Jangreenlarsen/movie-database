import { useEffect, useState } from "react";
import { api } from "../api/client";
import CinemaShowcase from "../components/CinemaShowcase";
import { formatShortDate, formatTime } from "../utils/cinemaFormat";
import { posterSrc } from "../utils/posterUrl";
import LanguagePicker from "../components/LanguagePicker";
import { useLocale, useT } from "../i18n";
import "./CinemaPublic.css";
// Feature #118 — genbruger den indloggede Voldby BIO-fanes brede kort-styling
// (.cinema-card*) på den offentlige side i stedet for at duplikere den.
import "./Cinema.css";
import "./Login.css";

// Feature #160 — Jans presse-PDF og byggeri-galleri, begge statiske filer i
// frontend/public/cinema/ (ikke en del af databasen). `encodeURI` fordi
// filnavnene har mellemrum/æøå, som ellers ikke er gyldige rå URL-tegn.
const PRESS_PDF_HREF = encodeURI("/cinema/Ny biograf åbner i Voldby 2026.pdf");
// #toolbar=0&navpanes=0 er browserens indbyggede PDF-visnings egne open-parameters
// (ikke noget vi kan style med CSS) — skjuler dens værktøjslinje/sidepanel i modal-visningen.
const PRESS_PDF_VIEWER_SRC = `${PRESS_PDF_HREF}#toolbar=0&navpanes=0`;
const GALLERY_DIR = "/cinema/Galleri/";

// Ingen backend-endpoint lister mappens indhold dynamisk (det er statiske
// filer i Vites public-mappe, ikke database-poster) — denne liste skal
// opdateres manuelt når nogen tilføjer/fjerner filer i Galleri-mappen.
const GALLERY_ITEMS = [
  { file: "byggeri1.jpg", type: "image" },
  { file: "byggeri2.jpg", type: "image" },
  { file: "byggeri3.jpg", type: "image" },
  { file: "byggeri4.jpg", type: "image" },
  { file: "byggeri5.jpg", type: "image" },
  { file: "byggeri5-HT.mp4", type: "video" },
  { file: "byggeri6.jpg", type: "image" },
  { file: "byggeri7.jpg", type: "image" },
  { file: "byggeri8.jpg", type: "image" },
  { file: "byggeri9.jpg", type: "image" },
  { file: "byggeri10.jpg", type: "image" },
  { file: "Stole.jpg", type: "image" },
  { file: "HT test1.MOV", type: "video" },
];

// Feature #70 — public, no-login page at /bio. Read-only: no admin tools,
// no "ønsk visning"/anmeldelses-knapper, just the showcase section + the
// upcoming program. Deliberately a separate component from Cinema.jsx
// rather than a "publicOnly" prop on it — Cinema.jsx assumes a logged-in
// `user` throughout (role checks, screening-request actions), and keeping
// the public route as its own simple component avoids having to thread a
// "no user" case through all of that.
//
// v2 (Jans feedback 2026-08-03): "Om Voldby BIO" moved back above the
// program, and every upcoming screening now sits in one flat side-by-side
// poster grid instead of being grouped under full per-day headings — with
// mostly one screening per day, date-grouping just produced a long single
// column of near-empty rows.
export default function CinemaPublic({ user = null, language, onLanguageChange }) {
  const t = useT();
  // BUGS.md #53 — åben/lukket-tilstanden ligger her frem for i
  // PublicLoginToggle, fordi knappen og panelet nu står to forskellige
  // steder i træet.
  const [loginOpen, setLoginOpen] = useState(false);
  const [galleryOpen, setGalleryOpen] = useState(false);
  const [pressOpen, setPressOpen] = useState(false);
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

  // Feature #125 — registrér det offentlige /bio-besøg (tælles som "gæst" hvis
  // ikke logget ind). Fire-and-forget, så en fejl aldrig påvirker siden.
  useEffect(() => {
    api.recordVisit({ page: "bio" }).catch(() => {});
  }, []);

  return (
    <div className="cinema-public-page">
      {/* Feature #119 — `baggrund2.png` som stemningsfuldt top-motiv bag
          hero'en (afløser #105's slørede skilt-baggrund). `aria-hidden`: rent
          dekorativt. Ligger som søskende til .cinema-public-hero (ikke inde i),
          så dens `position: absolute` regner sin højde ud fra hele
          .cinema-public-page og ikke bliver klemt af hero'ens egen indpakning.
          Se CinemaPublic.css for udtoning + dæmpning. */}
      <div className="cinema-public-backdrop" aria-hidden="true" />
      <header className="cinema-public-hero">
        {/* Feature #99 — sprogvalget står ved siden af login-knappen, ikke i
            modsatte hjørne: de to hører sammen som "det du gør før du er
            logget ind". Login-knappen står først (Jans ønske 2026-08-09).

            BUGS.md #57 — kun *knappen* bor her i hero'en. Selve login-/opret-
            dialogen er nu et centreret modal-overlay (renderet sidst i
            .cinema-public-page, se nedenfor), så den ikke længere afhænger af
            hero'ens højde eller stacking. Et tidligere forsøg placerede
            panelet absolut i hero'en; i portræt var hero'en for kort, så
            panelet flød ud under den og blev dækket af hovedindholdet, der
            opsnappede trykkene på "Opret bruger". */}
        <div className="cinema-public-hero-actions">
          <PublicLoginToggle user={user} open={loginOpen} onToggle={() => setLoginOpen((v) => !v)} />
          {onLanguageChange && (
            <LanguagePicker language={language} onChange={onLanguageChange} />
          )}
        </div>
        {/* Feature #104 — Voldby BIOs eget skilt som topbillede, i stedet for
            en tekst-overskrift på en accent-gradient. `<h1>` ombryder
            billedet frem for at stå separat: en skærmlæser skal stadig have
            en rigtig overskrift, og alt-teksten på billedet giver den —
            uden behov for en visuelt skjult duplikat-tekst ved siden af. */}
        <h1 className="cinema-public-sign">
          <img src="/cinema/voldby-bio-sign.jpg" alt={t("public.signAlt")} />
        </h1>
        <p className="cinema-public-tagline">{t("public.tagline")}</p>
      </header>

      <main className="cinema-public-main">
        <section>
          <div className="cinema-public-section-heading-row">
            <h2 className="cinema-public-section-heading">{t("public.about")}</h2>
            <button
              type="button"
              className="cinema-public-press-btn"
              onClick={() => setPressOpen(true)}
            >
              📰 {t("public.pressNews")}
            </button>
            <button
              type="button"
              className="cinema-public-gallery-btn"
              onClick={() => setGalleryOpen(true)}
            >
              🖼️ {t("public.gallery")}
            </button>
          </div>
          <CinemaShowcase />
        </section>

        <section>
          <h2 className="cinema-public-section-heading">{t("public.nowShowing")}</h2>
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

      {/* BUGS.md #57 — login-/opret-dialogen som centreret modal-overlay.
          `position: fixed` gør den viewport-centreret uanset hero-højde og
          orientering; den ligger sidst i .cinema-public-page, men fixed-
          elementer klippes ikke af containerens overflow, og der er intet
          transform/filter-ancestor her, så den centreres mod viewporten. */}
      {loginOpen && !user && (
        <PublicLoginPanel language={language} onClose={() => setLoginOpen(false)} />
      )}

      {galleryOpen && <GalleryModal onClose={() => setGalleryOpen(false)} />}

      {pressOpen && <PressModal onClose={() => setPressOpen(false)} />}
    </div>
  );
}

// Feature #161 — Jans ønske: en tilbage-knap i stedet for at åbne PDF'en i
// en helt separat browser-fane uden nogen vej tilbage til /bio. Samme
// overlay-panel som GalleryModal (genbruger dets CSS via en fælles klasse),
// men med et <iframe> i stedet for et grid. iOS/desktop Safari og Chrome
// kan alle vise en PDF inde i et iframe med deres indbyggede PDF-viewer;
// "Åbn i ny fane" står med som fallback for den sjældne browser der ikke kan.
function PressModal({ onClose }) {
  const t = useT();
  return (
    <div
      className="cinema-public-gallery-overlay"
      role="dialog"
      aria-modal="true"
      onClick={onClose}
    >
      <div
        className="cinema-public-gallery-panel cinema-public-press-panel"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="cinema-public-gallery-header">
          <button type="button" className="cinema-public-gallery-back" onClick={onClose}>
            ← {t("common.back")}
          </button>
          <a
            className="cinema-public-press-newtab"
            href={PRESS_PDF_HREF}
            target="_blank"
            rel="noreferrer"
          >
            {t("public.pressOpenNewTab")}
          </a>
        </div>
        <iframe
          className="cinema-public-press-frame"
          src={PRESS_PDF_VIEWER_SRC}
          title={t("public.pressNews")}
        />
      </div>
    </div>
  );
}

// Feature #160 — byggeri-galleriet. Samme centrerede overlay-mønster som
// PublicLoginPanel (BUGS.md #57), bare bredere til et billed-grid.
// Feature #161 — billeder åbner nu i et lightbox-underview med Forrige/
// Næste-navigation i stedet for direkte i en ny fane (Jans ønske: "vi
// mangler navigation på de billeder"), med en tilbage-knap til gridet.
// Videoer forbliver klikbare direkte i gridet (native afspiller-kontroller)
// — at gøre dem til endnu en lightbox-knap ville forhindre et klik på
// afspil-knappen i at virke, se koden nedenfor.
function GalleryModal({ onClose }) {
  const t = useT();
  const [lightboxIndex, setLightboxIndex] = useState(null);
  const activeItem = lightboxIndex != null ? GALLERY_ITEMS[lightboxIndex] : null;

  function showPrev() {
    setLightboxIndex((i) => (i - 1 + GALLERY_ITEMS.length) % GALLERY_ITEMS.length);
  }

  function showNext() {
    setLightboxIndex((i) => (i + 1) % GALLERY_ITEMS.length);
  }

  return (
    <div
      className="cinema-public-gallery-overlay"
      role="dialog"
      aria-modal="true"
      onClick={onClose}
    >
      <div className="cinema-public-gallery-panel" onClick={(e) => e.stopPropagation()}>
        <div className="cinema-public-gallery-header">
          {activeItem ? (
            <button
              type="button"
              className="cinema-public-gallery-back"
              onClick={() => setLightboxIndex(null)}
            >
              ← {t("common.back")}
            </button>
          ) : (
            <h2>{t("public.gallery")}</h2>
          )}
          <button
            type="button"
            className="cinema-public-gallery-close"
            onClick={onClose}
            aria-label={t("public.galleryClose")}
          >
            ✕
          </button>
        </div>
        {activeItem ? (
          <div className="cinema-public-gallery-lightbox">
            <button
              type="button"
              className="cinema-public-gallery-nav cinema-public-gallery-nav-prev"
              onClick={showPrev}
              aria-label={t("public.galleryPrev")}
            >
              ‹
            </button>
            {activeItem.type === "video" ? (
              <video
                key={activeItem.file}
                className="cinema-public-gallery-lightbox-media"
                controls
                preload="metadata"
              >
                <source src={encodeURI(`${GALLERY_DIR}${activeItem.file}`)} />
                {t("public.galleryVideoUnsupported")}
              </video>
            ) : (
              <img
                key={activeItem.file}
                className="cinema-public-gallery-lightbox-media"
                src={encodeURI(`${GALLERY_DIR}${activeItem.file}`)}
                alt=""
              />
            )}
            <button
              type="button"
              className="cinema-public-gallery-nav cinema-public-gallery-nav-next"
              onClick={showNext}
              aria-label={t("public.galleryNext")}
            >
              ›
            </button>
          </div>
        ) : (
          <div className="cinema-public-gallery-grid">
            {GALLERY_ITEMS.map((item, index) => {
              const src = encodeURI(`${GALLERY_DIR}${item.file}`);
              return item.type === "video" ? (
                <video
                  key={item.file}
                  className="cinema-public-gallery-item"
                  controls
                  preload="metadata"
                >
                  <source src={src} />
                  {t("public.galleryVideoUnsupported")}
                </video>
              ) : (
                <button
                  key={item.file}
                  type="button"
                  className="cinema-public-gallery-item cinema-public-gallery-item-button"
                  onClick={() => setLightboxIndex(index)}
                >
                  <img src={src} alt="" loading="lazy" />
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

// Feature #82 — Jans ønske: en besøgende på den delte, ikke-autentificerede
// /bio-side skal kunne logge ind direkte her i stedet for selv at skulle
// vide at navigere til "/". Et vellykket login sender browseren til "/"
// med en rigtig navigation (appen har ingen router og bruger allerede en
// ren pathname-check for /bio, jf. kommentaren i App.jsx) — der tager
// App.jsx over med den nu autentificerede bruger, landet på Voldby BIO
// (samme feature #82's anden halvdel: login lander altid der).
//
// BUGS.md #53 — knappen og selve panelet er to komponenter, fordi de skal
// stå to forskellige steder i træet: knappen sammen med sprogvalget i den
// absolut placerede hjørne-gruppe, panelet som søskende direkte i hero'en,
// hvor det kan få sin egen bredde.
function PublicLoginToggle({ user, open, onToggle }) {
  const t = useT();

  // Feature #84 — someone already signed in shouldn't be offered a login
  // form on what is now also the site's front page; send them into the app
  // instead. `user` is `undefined` while the session check is still in
  // flight, which correctly falls through to the login badge — the public
  // page must never block on that lookup (see App.jsx), and the badge
  // simply upgrades itself once the session resolves.
  if (user) {
    return (
      <a className="cinema-public-login-toggle" href="/">
        {t("public.openLibrary")}
      </a>
    );
  }

  // Knappen bliver stående mens panelet er åbent — dels så hjørne-gruppen
  // ikke skifter bredde og rykker sprogvalget rundt, dels så den kan lukke
  // panelet igen.
  return (
    <button
      type="button"
      className={`cinema-public-login-toggle${open ? " active" : ""}`}
      onClick={onToggle}
      aria-expanded={open}
    >
      {t("auth.login")}
    </button>
  );
}

function PublicLoginPanel({ language, onClose }) {
  const t = useT();
  // Feature #83 — samme to-tilstands-mønster som appens egen Login.jsx, så
  // en besøgende der har fået biograf-linket delt også kan oprette sin konto
  // her i stedet for først at skulle finde appens forside.
  const [mode, setMode] = useState("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  function switchMode(nextMode) {
    setMode(nextMode);
    setError(null);
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (mode === "login") {
        await api.login(username, password);
      } else {
        // Nye konti er `pending` (feature #66) — App.jsx viser så
        // "afventer godkendelse"-siden efter navigationen, præcis som når
        // man registrerer fra forsiden. Derfor samme redirect i begge
        // tilstande frem for en særskilt kvitteringsbesked her.
        // Feature #97 — se den identiske note i Login.jsx.
        await api.register(username, password, language, fullName);
      }
      window.location.assign("/");
    } catch (err) {
      setError(err.message);
      setSubmitting(false);
    }
  }

  return (
    <div
      className="cinema-public-login-overlay"
      role="dialog"
      aria-modal="true"
      onClick={onClose}
    >
      {/* stopPropagation: klik inde i selve dialogen må ikke lukke den — kun
          klik på det mørke backdrop udenom (eller Annullér-knappen). */}
      <div className="cinema-public-login-panel" onClick={(e) => e.stopPropagation()}>
        <form className="auth-form" onSubmit={handleSubmit}>
        {/* Feature #140 — obligatorisk fuldt navn ved oprettelse (kun i
            opret-tilstand), så en admin kan se hvem der beder om adgang. */}
        {mode === "register" && (
          <label>
            {t("auth.fullName")}
            <input
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              autoComplete="name"
              placeholder={t("auth.fullNamePlaceholder")}
              required
            />
          </label>
        )}
        <label>
          {t("auth.username")}
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            autoCapitalize="off"
            autoCorrect="off"
            spellCheck={false}
            required
            autoFocus
          />
        </label>
        <label>
          {t("auth.password")}
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            minLength={mode === "register" ? 8 : undefined}
            required
          />
        </label>
        {error && <div className="banner banner-error">{error}</div>}
        <div className="cinema-public-login-actions">
          <button type="button" className="btn" onClick={onClose} disabled={submitting}>
            {t("common.cancel")}
          </button>
          <button type="submit" className="btn btn-primary" disabled={submitting}>
            {t(
              submitting
                ? mode === "login"
                  ? "public.loggingIn"
                  : "public.creating"
                : mode === "login"
                  ? "auth.login"
                  : "public.createUser"
            )}
          </button>
        </div>
        <div className="auth-switch">
          {mode === "login" ? (
            <>
              {t("auth.noAccount")}{" "}
              <button type="button" onClick={() => switchMode("register")}>
                {t("public.createUser")}
              </button>
            </>
          ) : (
            <>
              {t("auth.haveAccount")}{" "}
              <button type="button" onClick={() => switchMode("login")}>
                {t("auth.login")}
              </button>
            </>
          )}
        </div>
        </form>
      </div>
    </div>
  );
}

// Feature #118 — samme brede kort-layout som den indloggede Voldby BIO-fanes
// `ScreeningCard` (Cinema.jsx), så en besøgende ser plot + trailer + IMDb som
// hvis de var logget ind. Genbruger `.cinema-card*` fra Cinema.css frem for
// dupликeret styling; den offentlige udgave har blot ingen admin-værktøjer, og
// tids-badgen viser dato+tid, da den offentlige liste er flad (ingen
// dag-gruppering — bevidst valg fra #64 v2).
function PublicScreeningCard({ screening }) {
  const t = useT();
  const locale = useLocale();
  return (
    <div className="cinema-card cinema-card--public">
      <div className="cinema-card-poster">
        {screening.poster_url ? (
          <img src={posterSrc(screening.poster_url, "w342")} alt={screening.title ?? ""} loading="lazy" />
        ) : (
          <span>{screening.media_kind === "movie" ? "🎬" : "📺"}</span>
        )}
      </div>
      <div className="cinema-card-body">
        {/* Feature #120 — dato/tid-badgen placeres i kortets øverste højre
            hjørne via .cinema-card--public (se CinemaPublic.css). */}
        <div className="cinema-card-time">
          {formatShortDate(screening.scheduled_at, locale)} ·{" "}
          {formatTime(screening.scheduled_at, locale)}
        </div>
        <h3 className="cinema-card-title">
          {screening.title ?? t("cinema.unknownTitle")}
          {screening.year ? ` (${screening.year})` : ""}
        </h3>
        {screening.genres?.length > 0 && (
          <div className="cinema-card-genres">{screening.genres.join(", ")}</div>
        )}
        {screening.overview && <p className="cinema-card-overview">{screening.overview}</p>}
        {screening.note && <p className="cinema-card-note">📝 {screening.note}</p>}
        {(screening.trailer_url || screening.imdb_url) && (
          <div className="cinema-card-links">
            {screening.trailer_url && (
              <a href={screening.trailer_url} target="_blank" rel="noreferrer">
                {t("cinema.watchTrailer")}
              </a>
            )}
            {screening.imdb_url && (
              <a href={screening.imdb_url} target="_blank" rel="noreferrer">
                IMDb
              </a>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
