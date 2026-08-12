import { useEffect, useState } from "react";
import Library from "./pages/Library";
import TvShows from "./pages/TvShows";
import Wishlist from "./pages/Wishlist";
import Settings from "./pages/Settings";
import PrintList from "./pages/PrintList";
import Statistics from "./pages/Statistics";
import Cinema from "./pages/Cinema";
import CinemaPublic from "./pages/CinemaPublic";
import Login from "./pages/Login";
import MessageBanner from "./components/MessageBanner";
import PendingApproval from "./pages/PendingApproval";
import { api } from "./api/client";
import I18nProvider from "./i18n/I18nProvider";
import { SOURCE_LANGUAGE, readStoredLanguage, storeLanguage, useT } from "./i18n";
import "./App.css";

// Feature #112 — browser-tilbage-knappen skal kunne bladre gennem fanerne.
// Ingen router-bibliotek (samme begrundelse som /bio og /login's rene
// pathname-tjek nedenfor): et hash er nok til at give hver fane sin egen
// historik-post uden at pille ved pathname, som /bio og /login allerede
// bruger. `window.location.hash = "..."` skubber selv en historik-post og
// udløser `hashchange` — ingen manuel `history.pushState` nødvendig.
const TAB_NAMES = ["library", "tv", "wishlist", "cinema", "print", "stats", "settings"];
// Faner en guest ikke må lande på via et gammelt/delt hash-link — se
// AppShell's identiske `!isGuest`-betingelser i navigationen.
// Feature #116 — Ønsker er ikke længere spærret: gæster må oprette ønsker.
const GUEST_RESTRICTED_TABS = ["print", "stats"];

function tabFromHash() {
  const hash = window.location.hash.slice(1);
  return TAB_NAMES.includes(hash) ? hash : "cinema";
}

/**
 * Feature #89 — sproget kommer fra brugerens egne indstillinger, så det
 * følger med på tværs af enheder. De offentlige skærme (Voldby BIO på /bio
 * og login) har ingen bruger at læse fra og bliver derfor på kildesproget;
 * det er den bevidste konsekvens af at gemme sproget i databasen frem for
 * i browseren (Jans valg 2026-08-08).
 */
function App() {
  // Jans ønske 2026-08-04: efter login lander man på Voldby BIO i stedet
  // for filmbiblioteket — gælder både et frisk login og en genindlæst side
  // med en allerede gyldig session, da begge ender her. Initialiseres fra et
  // evt. hash i URL'en, så et direkte/delt link til en bestemt fane (eller
  // et tryk på tilbage-knappen efter en genindlæsning) rammer rigtigt.
  const [tab, setTabState] = useState(tabFromHash);
  // Feature #97 — sproget på de skærme der kommer før login. Ligger i
  // localStorage, ikke i databasen: der er ingen bruger at gemme det på
  // endnu. Så snart man er logget ind, vinder kontoens eget sprog.
  const [preAuthLanguage, setPreAuthLanguage] = useState(readStoredLanguage);

  function choosePreAuthLanguage(code) {
    storeLanguage(code);
    setPreAuthLanguage(code);
  }

  const [user, setUser] = useState(undefined); // undefined = checking, null = logged out
  const [versionInfo, setVersionInfo] = useState(null);
  // Feature #72 — se den identiske note nedenfor ved AppShell-kaldet. Regnet
  // ud her (ikke kun nede ved returnen) så hash-vagten nedenfor kan bruge
  // den, uden at bryde reglen om at hooks altid kaldes ubetinget.
  const isGuest = user?.role === "guest";

  // Feature #112 — selve tilbage-knap-koblingen: et fane-skift sætter
  // hash'et, og `hashchange` (udløst af browserens frem/tilbage-knapper
  // lige såvel som af linjen ovenfor) er den ENESTE ting der opdaterer
  // `tab`-state — ét kodespor for begge veje ind, i stedet for at skulle
  // holde et programmatisk sæt og en event-lytter synkroniseret hver for
  // sig.
  function setTab(next) {
    if (next === tab) return;
    window.location.hash = next;
  }

  useEffect(() => {
    function onHashChange() {
      setTabState(tabFromHash());
    }
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  // En guest der lander på en begrænset fane via et gammelt hash (fx et
  // bogmærke sat dengang de var standard-bruger) sendes til Voldby BIO i
  // stedet for at se en fane der reelt intet indhold viser for dem.
  useEffect(() => {
    if (isGuest && GUEST_RESTRICTED_TABS.includes(tab)) {
      setTab("cinema");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isGuest, tab]);

  useEffect(() => {
    api
      .me()
      .then(setUser)
      .catch(() => setUser(null));
    api
      .health()
      .then((data) => setVersionInfo({ version: data.version, build: data.build }))
      .catch(() => {});
  }, []);

  // Feature #110 — personligt tema. Sat her (øverst i App, uafhængigt af
  // hvilken betinget gren der rent faktisk returneres — login,
  // afventer-godkendelse, den autentificerede app) frem for i en dedikeret
  // provider, da intet andet i træet behøver temaet som en værdi; CSS'ens
  // egne :root[data-theme="..."]-blokke (index.css) gør resten. Spejler
  // I18nProvider's `document.documentElement.lang`-mønster. Intet valgt
  // (usat bruger, eller endnu ingen bruger) fjerner attributten helt, så
  // `prefers-color-scheme` i CSS'en får lov at afgøre det i stedet.
  useEffect(() => {
    // Feature #121 (Jans ønske 2026-08-11) — mørkt tema er nu default. En usat
    // bruger (eller endnu ingen bruger: den offentlige /bio-side og login-siden)
    // får "dark" i stedet for at følge systemets `prefers-color-scheme` som før
    // (#110). Et eksplicit personligt valg (light/dark) vinder stadig.
    const theme = user?.settings?.theme;
    document.documentElement.setAttribute("data-theme", theme || "dark");
  }, [user?.settings?.theme]);

  async function handleLogout() {
    await api.logout();
    setUser(null);
  }

  // Feature #70 — /bio is a public, no-login page (shareable outside the
  // app), checked before any auth state so it never waits on or requires
  // a login check. No router library: these are the only routes that need
  // to exist outside the tab-based authenticated app, so plain pathname
  // checks are simpler than pulling in react-router. Caddy's
  // `try_files {path} /index.html` (see DEPLOYMENT.md) and Vite's dev
  // server both already serve index.html for any unmatched path, so a
  // direct/shared link works without further server config.
  //
  // `user` is passed through (possibly still `undefined` while the session
  // check is in flight) purely so the login badge can offer "Åbn
  // biblioteket" to someone already signed in — the page itself renders
  // immediately either way, which is the whole point of this early return.
  if (window.location.pathname.startsWith("/bio")) {
    // Feature #89 — en besøgende uden login har intet sprogvalg at læse, så
    // siden bliver på kildesproget. Er man derimod allerede logget ind (den
    // delte /bio-adresse er også en genvej for husets egne brugere),
    // kender vi præferencen og bruger den.
    return (
      <I18nProvider language={user?.settings?.language ?? preAuthLanguage}>
        <CinemaPublic
          user={user}
          language={preAuthLanguage}
          onLanguageChange={choosePreAuthLanguage}
        />
      </I18nProvider>
    );
  }

  // Feature #84 — the full login page keeps its own URL so it isn't
  // orphaned by the landing-page change below, and so there's still a
  // direct link for "just let me sign in".
  if (window.location.pathname.startsWith("/login")) {
    return (
      <I18nProvider language={preAuthLanguage}>
        <Login
          onAuthenticated={setUser}
          language={preAuthLanguage}
          onLanguageChange={choosePreAuthLanguage}
        />
      </I18nProvider>
    );
  }

  if (user === undefined) {
    return null;
  }

  // Feature #84 — Voldby BIO is the public front door: a logged-out visitor
  // to "/" gets the cinema page (programme, showcase, and the login/opret
  // badge) rather than a bare login form, so the shared /bio link and the
  // site root are the same shop window.
  if (user === null) {
    return (
      <I18nProvider language={preAuthLanguage}>
        <CinemaPublic
          user={null}
          language={preAuthLanguage}
          onLanguageChange={choosePreAuthLanguage}
        />
      </I18nProvider>
    );
  }

  if (user.status !== "active") {
    return (
      <I18nProvider language={user.settings?.language ?? SOURCE_LANGUAGE}>
        <PendingApproval user={user} onLogout={handleLogout} />
      </I18nProvider>
    );
  }

  // Feature #72 — guest is read-only: Print/Statistik aren't part of "se
  // film/TV-bibliotek", so they're hidden entirely rather than just disabled.
  // Feature #116 — Ønsker er nu åben for gæster (de må oprette ønsker, men
  // ikke sætte bestillingsstatus); selve add-/status-gatingen sker i Library/
  // TvShows og håndhæves i backend (`enforce_guest_wishlist_only`).

  return (
    <I18nProvider language={user.settings?.language ?? SOURCE_LANGUAGE}>
      <AppShell
        user={user}
        isGuest={isGuest}
        tab={tab}
        setTab={setTab}
        setUser={setUser}
        versionInfo={versionInfo}
        onLogout={handleLogout}
      />
    </I18nProvider>
  );
}

function AppShell({ user, isGuest, tab, setTab, setUser, versionInfo, onLogout }) {
  const t = useT();
  // Feature #94 — samlet optælling i hovedet, så man kan se biblioteksets
  // størrelse fra enhver side uden at navigere hen til statistikken.
  // `libraryVersion` tvinger en genhentning når noget er gemt eller slettet;
  // uden den ville tallet blive stående til næste sideindlæsning.
  const [libraryVersion, setLibraryVersion] = useState(0);
  const [counts, setCounts] = useState(null);

  useEffect(() => {
    api.getLibraryCounts().then(setCounts).catch(() => setCounts(null));
  }, [libraryVersion]);

  // Feature #125 — registrér et side-besøg ved hvert fane-skift (og ved
  // første indlæsning). Fire-and-forget: en fejlet registrering må aldrig
  // forstyrre navigationen.
  useEffect(() => {
    api.recordVisit({ page: tab }).catch(() => {});
  }, [tab]);

  const refreshCounts = () => setLibraryVersion((v) => v + 1);

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-header-inner">
          <div className="brand">
            <span className="brand-mark" aria-hidden="true">
              🎬
            </span>
            {t("app.brand")}
          </div>
          <nav className="tabs">
            <button
              className={tab === "library" ? "active" : ""}
              onClick={() => setTab("library")}
            >
              {t("app.nav.movies")}
            </button>
            <button
              className={tab === "tv" ? "active" : ""}
              onClick={() => setTab("tv")}
            >
              {t("app.nav.tv")}
            </button>
            <button
              className={tab === "wishlist" ? "active" : ""}
              onClick={() => setTab("wishlist")}
            >
              {t("app.nav.wishlist")}
            </button>
            <button
              className={tab === "cinema" ? "active" : ""}
              onClick={() => setTab("cinema")}
            >
              {t("app.nav.cinema")}
            </button>
            {!isGuest && (
              <button
                className={tab === "print" ? "active" : ""}
                onClick={() => setTab("print")}
              >
                {t("app.nav.print")}
              </button>
            )}
            {!isGuest && (
              <button
                className={tab === "stats" ? "active" : ""}
                onClick={() => setTab("stats")}
              >
                {t("app.nav.stats")}
              </button>
            )}
            <button
              className={tab === "settings" ? "active" : ""}
              onClick={() => setTab("settings")}
            >
              {t("app.nav.settings")}
            </button>
          </nav>
          <div className="header-user">
            {counts && (
              <span
                className="header-counts"
                title={t("counts.title", {
                  movies: counts.movies.total,
                  movePhysical: counts.movies.physical,
                  movieDigital: counts.movies.digital,
                  shows: counts.tv_shows.total,
                  showPhysical: counts.tv_shows.physical,
                  showDigital: counts.tv_shows.digital,
                })}
              >
                {/* To separate mærkater frem for én streng: film og
                    TV-serier er to adskilte ressourcer, og hvert tal skal
                    kunne aflæses for sig uden at man læser en sætning.
                    Feature #107 — fordelingen på fysisk/digital stod før kun
                    i hover-teksten (usynlig på en telefon uden mus); den
                    står nu i selve mærkatet, i sit eget span, så den kan
                    skjules på en smal skærm (se media query i App.css) uden
                    at totaltallet også forsvinder. */}
                <span className="header-count header-count--movies">
                  {t("counts.movies", { count: counts.movies.total })}
                  <span className="header-count-breakdown">
                    {t("counts.breakdown", {
                      physical: counts.movies.physical,
                      digital: counts.movies.digital,
                    })}
                  </span>
                </span>
                <span className="header-count header-count--shows">
                  {t("counts.shows", { count: counts.tv_shows.total })}
                  <span className="header-count-breakdown">
                    {t("counts.breakdown", {
                      physical: counts.tv_shows.physical,
                      digital: counts.tv_shows.digital,
                    })}
                  </span>
                </span>
              </span>
            )}
            <span className="muted">{user.username}</span>
            <button type="button" className="btn" onClick={onLogout}>
              {t("app.logout")}
            </button>
          </div>
        </div>
      </header>

      <main className="app-main">
        {/* Feature #100 — beskeder står øverst i indholdet, ikke i hovedet:
            de kan fylde flere linjer, og et hoved der vokser ville skubbe
            hele siden ned hver gang der kommer en ny. */}
        <MessageBanner />
        {tab === "library" && (
          <Library
            user={user}
            onSettingsChanged={setUser}
            onGoToTvShows={() => setTab("tv")}
            onLibraryChanged={refreshCounts}
          />
        )}
        {tab === "tv" && (
          <TvShows
            user={user}
            onSettingsChanged={setUser}
            onGoToMovies={() => setTab("library")}
            onLibraryChanged={refreshCounts}
          />
        )}
        {tab === "wishlist" && (
          <Wishlist user={user} onSettingsChanged={setUser} onLibraryChanged={refreshCounts} />
        )}
        {tab === "cinema" && <Cinema user={user} />}
        {!isGuest && tab === "print" && <PrintList />}
        {!isGuest && tab === "stats" && <Statistics />}
        {tab === "settings" && <Settings user={user} onSettingsChanged={setUser} />}
      </main>

      <footer className="app-footer">
        <span className="muted">
          {versionInfo ? `v${versionInfo.version} (build ${versionInfo.build})` : ""}
        </span>
      </footer>
    </div>
  );
}

export default App;
