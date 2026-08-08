import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useT } from "../i18n";
import { MOVIE_SERIAL_PREFIX, TV_SERIAL_PREFIX, formatSerial } from "../utils/serialNumber";
import "./PrintList.css";

export default function PrintList() {
  const t = useT();
  const [movies, setMovies] = useState([]);
  const [shows, setShows] = useState([]);
  const [status, setStatus] = useState("loading");
  const [query, setQuery] = useState("");
  const [serialPaddingWidth, setSerialPaddingWidth] = useState(0);

  useEffect(() => {
    api
      .getSerialNumberConfig()
      .then((config) => setSerialPaddingWidth(config.padding_width))
      .catch(() => {});
  }, []);

  useEffect(() => {
    setStatus("loading");
    Promise.all([
      api.listMovies({ q: query || undefined, sort: "serial_number:asc" }),
      api.listTvShows({ q: query || undefined, sort: "serial_number:asc" }),
    ])
      .then(([movieData, showData]) => {
        setMovies(movieData.items);
        setShows(showData.items);
        setStatus("ready");
      })
      .catch(() => setStatus("error"));
  }, [query]);

  return (
    <section className="print-page">
      <div className="page-header no-print">
        <h1>{t("print.title")}</h1>
        <button type="button" className="btn btn-primary" onClick={() => window.print()}>
          {t("print.print")}
        </button>
      </div>

      <div className="no-print print-search">
        <input
          type="search"
          placeholder={t("lib.searchPlaceholder")}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
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
                  <th>{t("print.serialShort")}</th>
                  <th>{t("field.title")}</th>
                  <th>{t("field.year")}</th>
                  <th>{t("field.format")}</th>
                  <th>{t("field.location")}</th>
                </tr>
              </thead>
              <tbody>
                {movies.map((movie) => (
                  <tr key={movie.id}>
                    <td>
                      {formatSerial(movie.serial_number, serialPaddingWidth, MOVIE_SERIAL_PREFIX)}
                    </td>
                    <td>{movie.title}</td>
                    <td>{movie.year ?? ""}</td>
                    <td>{movie.format ?? ""}</td>
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
                  <th>{t("print.serialShort")}</th>
                  <th>{t("field.name")}</th>
                  <th>{t("field.year")}</th>
                  <th>{t("field.seasons")}</th>
                  <th>{t("field.format")}</th>
                  <th>{t("field.location")}</th>
                </tr>
              </thead>
              <tbody>
                {shows.map((show) => (
                  <tr key={show.id}>
                    <td>
                      {formatSerial(show.serial_number, serialPaddingWidth, TV_SERIAL_PREFIX)}
                    </td>
                    <td>{show.name}</td>
                    <td>{show.year ?? ""}</td>
                    <td>
                      {show.number_of_seasons
                        ? `${show.seasons.filter((s) => s.owned).length}/${show.number_of_seasons}`
                        : ""}
                    </td>
                    <td>{show.format ?? ""}</td>
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
