import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import { useT } from "../i18n";
import { formatSerial, isDigitalMediaType, serialPrefix } from "../utils/serialNumber";
import "./PrintList.css";

/**
 * Feature #98 — kolonnerne kan sorteres.
 *
 * Nøglen er logisk, ikke et API-feltnavn: film og TV-serier hedder det samme
 * i overskriften ("Titel"/"Navn") men forskelligt i backenden, og de to
 * tabeller sorteres af det samme klik. Hver post oversætter derfor sig selv
 * til det rigtige felt pr. ressource.
 */
const SORTABLE_COLUMNS = {
  serial: { labelKey: "print.serialShort", movie: "serial_number", tv: "serial_number" },
  title: { labelKey: "field.title", movie: "title", tv: null },
  name: { labelKey: "field.name", movie: null, tv: "name" },
  year: { labelKey: "field.year", movie: "year", tv: "year" },
  format: { labelKey: "field.format", movie: "format", tv: "format" },
  audio: { labelKey: "field.audioType", movie: "audio_types", tv: "audio_types" },
  location: { labelKey: "field.location", movie: "location", tv: "location" },
};

function sortParam(columnKey, direction, resource) {
  const field = SORTABLE_COLUMNS[columnKey]?.[resource];
  // Kolonner der ikke findes for denne ressource (fx "Titel" på TV-tabellen)
  // falder tilbage til serienummeret, så listen stadig har en fast orden.
  return `${field ?? "serial_number"}:${direction}`;
}

/** Klikbar kolonne-overskrift. Pilen printes med, så en udskrift viser
 *  hvilken orden den blev lavet i. */
function SortableHeader({ columnKey, sort, onSort, children }) {
  const active = sort.column === columnKey;
  return (
    <th>
      <button type="button" className="print-sort-header" onClick={() => onSort(columnKey)}>
        {children}
        <span className="print-sort-arrow">{active ? (sort.direction === "asc" ? "▲" : "▼") : ""}</span>
      </button>
    </th>
  );
}

/**
 * Feature #158 — samme sektion vist to gange (digital/fysisk), samt genbrugt
 * af "print alt". Adskilt fra TV-varianten fordi kolonnerne reelt er
 * forskellige (Titel vs. Navn+Sæsoner), ikke bare navngivet forskelligt.
 */
function MoviesTable({ t, movies, sort, onSort, serialPaddingWidth }) {
  const headerProps = { sort, onSort };
  return (
    <table className="print-table">
      <thead>
        <tr>
          <SortableHeader columnKey="serial" {...headerProps}>
            {t("print.serialShort")}
          </SortableHeader>
          <SortableHeader columnKey="title" {...headerProps}>
            {t("field.title")}
          </SortableHeader>
          <SortableHeader columnKey="year" {...headerProps}>
            {t("field.year")}
          </SortableHeader>
          <SortableHeader columnKey="format" {...headerProps}>
            {t("field.format")}
          </SortableHeader>
          <SortableHeader columnKey="audio" {...headerProps}>
            {t("field.audioType")}
          </SortableHeader>
          <SortableHeader columnKey="location" {...headerProps}>
            {t("field.location")}
          </SortableHeader>
        </tr>
      </thead>
      <tbody>
        {movies.map((movie) => (
          <tr key={movie.id}>
            <td>
              {formatSerial(movie.serial_number, serialPaddingWidth, serialPrefix(movie.media_type, "movie"))}
            </td>
            <td>{movie.title}</td>
            <td>{movie.year ?? ""}</td>
            <td>{movie.format ?? ""}</td>
            <td>{movie.audio_types.join(", ")}</td>
            <td>{movie.location ?? ""}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ShowsTable({ t, shows, sort, onSort, serialPaddingWidth }) {
  const headerProps = { sort, onSort };
  return (
    <table className="print-table">
      <thead>
        <tr>
          <SortableHeader columnKey="serial" {...headerProps}>
            {t("print.serialShort")}
          </SortableHeader>
          <SortableHeader columnKey="name" {...headerProps}>
            {t("field.name")}
          </SortableHeader>
          <SortableHeader columnKey="year" {...headerProps}>
            {t("field.year")}
          </SortableHeader>
          {/* Sæson-tallet er beregnet ud fra `seasons[]` og findes ikke som
              et sorterbart felt i backenden. */}
          <th>{t("field.seasons")}</th>
          <SortableHeader columnKey="format" {...headerProps}>
            {t("field.format")}
          </SortableHeader>
          <SortableHeader columnKey="audio" {...headerProps}>
            {t("field.audioType")}
          </SortableHeader>
          <SortableHeader columnKey="location" {...headerProps}>
            {t("field.location")}
          </SortableHeader>
        </tr>
      </thead>
      <tbody>
        {shows.map((show) => (
          <tr key={show.id}>
            <td>{formatSerial(show.serial_number, serialPaddingWidth, serialPrefix(show.media_type, "tv"))}</td>
            <td>{show.name}</td>
            <td>{show.year ?? ""}</td>
            <td>
              {show.number_of_seasons
                ? `${show.seasons.filter((s) => s.owned).length}/${show.number_of_seasons}`
                : ""}
            </td>
            <td>{show.format ?? ""}</td>
            <td>{show.audio_types.join(", ")}</td>
            <td>{show.location ?? ""}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function PrintList() {
  const t = useT();
  const [movies, setMovies] = useState([]);
  const [shows, setShows] = useState([]);
  const [status, setStatus] = useState("loading");
  const [query, setQuery] = useState("");
  const [serialPaddingWidth, setSerialPaddingWidth] = useState(0);
  const [sort, setSort] = useState({ column: "serial", direction: "asc" });
  // Feature #158 — `null` printer hele siden (den oprindelige knap); en
  // sektionsnøgle printer *kun* den sektion, resten skjules via CSS mens
  // dialogen er åben og vises igen bagefter (se "afterprint" nedenfor).
  const [printOnly, setPrintOnly] = useState(null);

  function toggleSort(columnKey) {
    setSort((prev) =>
      prev.column === columnKey
        ? { column: columnKey, direction: prev.direction === "asc" ? "desc" : "asc" }
        : // Et nyt valg starter stigende: det er den forventede første
          // aflæsning af en liste, uanset hvad den forrige kolonne stod på.
          { column: columnKey, direction: "asc" }
    );
  }

  useEffect(() => {
    api
      .getSerialNumberConfig()
      .then((config) => setSerialPaddingWidth(config.padding_width))
      // Bevidst tavs: numrene udskrives blot uden foranstillede nuller.
      .catch(() => {});
  }, []);

  useEffect(() => {
    setStatus("loading");
    Promise.all([
      api.listMovies({ q: query || undefined, sort: sortParam(sort.column, sort.direction, "movie") }),
      api.listTvShows({ q: query || undefined, sort: sortParam(sort.column, sort.direction, "tv") }),
    ])
      .then(([movieData, showData]) => {
        setMovies(movieData.items);
        setShows(showData.items);
        setStatus("ready");
      })
      .catch(() => setStatus("error"));
  }, [query, sort]);

  // Feature #158 — digital/fysisk hver sin printbare liste (Jans ønske
  // 2026-08-15). Filtrering, ikke et separat API-kald: samme allerede
  // hentede/sorterede data genbruges, delt i to på klienten.
  const moviesDigital = useMemo(() => movies.filter((m) => isDigitalMediaType(m.media_type)), [movies]);
  const moviesPhysical = useMemo(() => movies.filter((m) => !isDigitalMediaType(m.media_type)), [movies]);
  const showsDigital = useMemo(() => shows.filter((s) => isDigitalMediaType(s.media_type)), [shows]);
  const showsPhysical = useMemo(() => shows.filter((s) => !isDigitalMediaType(s.media_type)), [shows]);

  useEffect(() => {
    if (printOnly) window.print();
  }, [printOnly]);

  useEffect(() => {
    // `afterprint` fyrer uanset om brugeren rent faktisk printede eller
    // annullerede dialogen — begge tilfælde skal bringe hele siden tilbage.
    function handleAfterPrint() {
      setPrintOnly(null);
    }
    window.addEventListener("afterprint", handleAfterPrint);
    return () => window.removeEventListener("afterprint", handleAfterPrint);
  }, []);

  const headerProps = { sort, onSort: toggleSort };

  // Rækkefølgen udskriften/skærmen viser sektionerne i.
  const sections = [
    {
      key: "movies-digital",
      title: t("print.moviesDigital"),
      count: t("print.movieCount", { count: moviesDigital.length }),
      table: <MoviesTable t={t} movies={moviesDigital} {...headerProps} serialPaddingWidth={serialPaddingWidth} />,
      length: moviesDigital.length,
    },
    {
      key: "movies-physical",
      title: t("print.moviesPhysical"),
      count: t("print.movieCount", { count: moviesPhysical.length }),
      table: <MoviesTable t={t} movies={moviesPhysical} {...headerProps} serialPaddingWidth={serialPaddingWidth} />,
      length: moviesPhysical.length,
    },
    {
      key: "shows-digital",
      title: t("print.showsDigital"),
      count: t("print.showCount", { count: showsDigital.length }),
      table: <ShowsTable t={t} shows={showsDigital} {...headerProps} serialPaddingWidth={serialPaddingWidth} />,
      length: showsDigital.length,
    },
    {
      key: "shows-physical",
      title: t("print.showsPhysical"),
      count: t("print.showCount", { count: showsPhysical.length }),
      table: <ShowsTable t={t} shows={showsPhysical} {...headerProps} serialPaddingWidth={serialPaddingWidth} />,
      length: showsPhysical.length,
    },
  ];
  let sawNonEmptySection = false;

  return (
    <section className={`print-page${printOnly ? " print-only-mode" : ""}`}>
      <div className="page-header no-print">
        <h1>{t("print.title")}</h1>
        <button type="button" className="btn btn-primary" onClick={() => window.print()}>
          {t("print.print")}
        </button>
      </div>

      <div className="no-print print-search">
        <div className="print-search-wrap">
          <input
            type="search"
            placeholder={t("lib.searchPlaceholder")}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          {/* Feature #102 — se noten i Library.jsx. */}
          {query && (
            <button
              type="button"
              className="search-clear"
              onClick={() => setQuery("")}
              title={t("lib.clearSearch")}
              aria-label={t("lib.clearSearch")}
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {status === "loading" && <p className="muted">{t("common.loading")}</p>}
      {status === "error" && (
        <div className="banner banner-error">{t("print.loadError")}</div>
      )}

      {status === "ready" &&
        sections.map((section) => {
          // BUGS.md #49 — hver ressource i sin egen `print-section`, så
          // sideskiftet sidder på et rigtigt blok-element frem for på en
          // overskrift midt i et fælles fragment. Ingen sideskift nødvendigt
          // når kun én sektion printes (`printOnly`) — den er jo alene.
          const needsBreak = sawNonEmptySection && !printOnly;
          if (section.length > 0) sawNonEmptySection = true;
          return (
            <section
              key={section.key}
              className={`print-section${needsBreak ? " print-page-break" : ""}${
                printOnly === section.key ? " print-section-only" : ""
              }`}
            >
              <div className="print-section-heading">
                <h2>{section.title}</h2>
                <button
                  type="button"
                  className="btn no-print"
                  onClick={() => setPrintOnly(section.key)}
                >
                  {t("print.printSection")}
                </button>
              </div>
              {section.table}
              <p className="muted no-print" style={{ marginTop: 12 }}>
                {section.count}
              </p>
            </section>
          );
        })}
    </section>
  );
}
