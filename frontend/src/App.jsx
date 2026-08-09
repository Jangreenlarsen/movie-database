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
import PendingApproval from "./pages/PendingApproval";
import { api } from "./api/client";
import I18nProvider from "./i18n/I18nProvider";
import { SOURCE_LANGUAGE, useT } from "./i18n";
import "./App.css";

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
  // med en allerede gyldig session, da begge ender her.
  const [tab, setTab] = useState("cinema");
  const [user, setUser] = useState(undefined); // undefined = checking, null = logged out
  const [versionInfo, setVersionInfo] = useState(null);

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
      <I18nProvider language={user?.settings?.language ?? SOURCE_LANGUAGE}>
        <CinemaPublic user={user} />
      </I18nProvider>
    );
  }

  // Feature #84 — the full login page keeps its own URL so it isn't
  // orphaned by the landing-page change below, and so there's still a
  // direct link for "just let me sign in".
  if (window.location.pathname.startsWith("/login")) {
    // Ingen bruger endnu — login-skærmen er altid på kildesproget.
    return <Login onAuthenticated={setUser} />;
  }

  if (user === undefined) {
    return null;
  }

  // Feature #84 — Voldby BIO is the public front door: a logged-out visitor
  // to "/" gets the cinema page (programme, showcase, and the login/opret
  // badge) rather than a bare login form, so the shared /bio link and the
  // site root are the same shop window.
  if (user === null) {
    return <CinemaPublic user={null} />;
  }

  if (user.status !== "active") {
    return (
      <I18nProvider language={user.settings?.language ?? SOURCE_LANGUAGE}>
        <PendingApproval user={user} onLogout={handleLogout} />
      </I18nProvider>
    );
  }

  // Feature #72 — guest is read-only: Ønsker/Print/Statistik all involve
  // either writing (ønske en film) or aren't part of "se film/TV-bibliotek",
  // so they're hidden entirely rather than just disabled.
  const isGuest = user.role === "guest";

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
            {!isGuest && (
              <button
                className={tab === "wishlist" ? "active" : ""}
                onClick={() => setTab("wishlist")}
              >
                {t("app.nav.wishlist")}
              </button>
            )}
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
                    kunne aflæses for sig uden at man læser en sætning. */}
                <span className="header-count header-count--movies">
                  {t("counts.movies", { count: counts.movies.total })}
                </span>
                <span className="header-count header-count--shows">
                  {t("counts.shows", { count: counts.tv_shows.total })}
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
        {!isGuest && tab === "wishlist" && (
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
