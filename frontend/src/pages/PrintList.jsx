import { useEffect, useState } from "react";
import { api } from "../api/client";
import "./PrintList.css";

function formatSerial(serialNumber, paddingWidth) {
  if (serialNumber == null) return "—";
  return `#${String(serialNumber).padStart(paddingWidth, "0")}`;
}

export default function PrintList() {
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
        <h1>Print-venlig liste</h1>
        <button type="button" className="btn btn-primary" onClick={() => window.print()}>
          🖨️ Print
        </button>
      </div>

      <div className="no-print print-search">
        <input
          type="search"
          placeholder="Søg på titel, skuespiller, genre..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      {status === "loading" && <p className="muted">Indlæser...</p>}
      {status === "error" && (
        <div className="banner banner-error">Kunne ikke hente film/TV-serier.</div>
      )}

      {status === "ready" && (
        <>
          <h2>Film</h2>
          <table className="print-table">
            <thead>
              <tr>
                <th>Serienr.</th>
                <th>Titel</th>
                <th>År</th>
                <th>Format</th>
                <th>Lokation</th>
              </tr>
            </thead>
            <tbody>
              {movies.map((movie) => (
                <tr key={movie.id}>
                  <td>{formatSerial(movie.serial_number, serialPaddingWidth)}</td>
                  <td>{movie.title}</td>
                  <td>{movie.year ?? ""}</td>
                  <td>{movie.format ?? ""}</td>
                  <td>{movie.location ?? ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted no-print" style={{ marginTop: 12 }}>
            {movies.length} film
          </p>

          <h2 className="print-section-break">TV-serier</h2>
          <table className="print-table">
            <thead>
              <tr>
                <th>Serienr.</th>
                <th>Navn</th>
                <th>År</th>
                <th>Sæsoner</th>
                <th>Format</th>
                <th>Lokation</th>
              </tr>
            </thead>
            <tbody>
              {shows.map((show) => (
                <tr key={show.id}>
                  <td>{formatSerial(show.serial_number, serialPaddingWidth)}</td>
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
            {shows.length} TV-serier
          </p>
        </>
      )}
    </section>
  );
}
