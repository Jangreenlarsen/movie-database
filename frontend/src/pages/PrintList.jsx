import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useT } from "../i18n";
import { formatSerial, serialPrefix } from "../utils/serialNumber";
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

export default function PrintList() {
  const t = useT();
  const [movies, setMovies] = useState([]);
  const [shows, setShows] = useState([]);
  const [status, setStatus] = useState("loading");
  const [query, setQuery] = useState("");
  const [serialPaddingWidth, setSerialPaddingWidth] = useState(0);
  const [sort, setSort] = useState({ column: "serial", direction: "asc" });

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

  const headerProps = { sort, onSort: toggleSort };

  return (
    <section className="print-page">
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

      {status === "ready" && (
        <>
          {/* BUGS.md #49 — hver ressource i sin egen `print-section`, så
              sideskiftet sidder på et rigtigt blok-element frem for på en
              overskrift midt i et fælles fragment. */}
          <section className="print-section">
            <h2>{t("app.nav.movies")}</h2>
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
            <p className="muted no-print" style={{ marginTop: 12 }}>
              {t("print.movieCount", { count: movies.length })}
            </p>
          </section>

          {/* Sideskiftet droppes hvis film-listen er tom — ellers ville
              udskriften starte med en tom side før TV-serierne. */}
          <section className={`print-section${movies.length > 0 ? " print-page-break" : ""}`}>
            <h2>{t("app.nav.tv")}</h2>
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
                  {/* Sæson-tallet er beregnet ud fra `seasons[]` og findes
                      ikke som et sorterbart felt i backenden. */}
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
                    <td>
                      {formatSerial(show.serial_number, serialPaddingWidth, serialPrefix(show.media_type, "tv"))}
                    </td>
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
            <p className="muted no-print" style={{ marginTop: 12 }}>
              {t("print.showCount", { count: shows.length })}
            </p>
          </section>
        </>
      )}
    </section>
  );
}
