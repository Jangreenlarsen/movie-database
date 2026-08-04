import { useEffect, useState } from "react";
import BarcodeScanner from "../scanner/BarcodeScanner";
import { api } from "../api/client";
import Chip from "./Chip";
import { MovieDetailModal } from "../pages/Library";
import { TvShowDetailModal } from "../pages/TvShows";
import "./MovieLookupForm.css";

function toggleValue(list, value) {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}

function emptyDraftFields(user, wishlist) {
  return {
    tags: [],
    format: null,
    audio_types: [],
    media_type: null,
    location: "",
    owner: user?.username ?? "",
    is_wishlist: wishlist,
    personal_rating: null,
    personal_note: null,
    watched: false,
    watched_at: null,
  };
}

/**
 * Barcode-scan + manual TMDb-search + vælg-kandidat flow. Shared by the
 * "Scan film" page (wishlist=false) og "Ønsker"-sektionens eget add-panel
 * (wishlist=true). Ved valg af en kandidat (feature #79) hentes en fuld,
 * rent læsende TMDb-forhåndsvisning, og den samme rediger-boks som bruges
 * for eksisterende bibliotekskort (`MovieDetailModal`/`TvShowDetailModal`)
 * åbnes i "kladde"-tilstand — intet gemmes i databasen før brugeren selv
 * trykker "Opret" i boksen.
 */
export default function MovieLookupForm({ user, wishlist = false, onSaved }) {
  const [barcode, setBarcode] = useState(null);
  const [barcodeSource, setBarcodeSource] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [scanStatus, setScanStatus] = useState("idle");
  const [manualBarcode, setManualBarcode] = useState("");
  const [manualQuery, setManualQuery] = useState("");
  const [manualStatus, setManualStatus] = useState("idle");

  const [selectedCandidate, setSelectedCandidate] = useState(null);
  const [attributeOptions, setAttributeOptions] = useState({
    formats: [],
    audio_types: [],
    media_types: [],
  });
  const [allTags, setAllTags] = useState([]);
  const [allOwners, setAllOwners] = useState([]);
  const [allLocations, setAllLocations] = useState([]);
  const [serialPaddingWidth, setSerialPaddingWidth] = useState(0);
  const [saveStatus, setSaveStatus] = useState("idle");
  const [lastSavedKind, setLastSavedKind] = useState("movie");
  const [duplicates, setDuplicates] = useState([]);

  // Sæson-gruppering (feature #53): når en scannet/søgt TV-serie allerede
  // findes, kan brugeren i stedet markere sæson(er) som ejet på den
  // eksisterende serie — undgår at hver ny sæson-boks (fx "The Americans
  // Season 2") opretter sin egen separate serie-post.
  const [existingTvShow, setExistingTvShow] = useState(null);
  // Sæsonvalg ved oprettelse af en HELT NY serie (feature #54): TMDb's
  // sæson-liste hentes til forhåndsvisning (uden at gemme noget), så
  // brugeren kan afkrydse hvilke sæsoner udgaven indeholder *før* der
  // springes videre til rediger-boksen.
  const [previewSeasons, setPreviewSeasons] = useState([]);
  const [selectedSeasonNumbers, setSelectedSeasonNumbers] = useState([]);
  const [groupStatus, setGroupStatus] = useState("idle");
  const [groupError, setGroupError] = useState(null);
  const [groupSavedShowName, setGroupSavedShowName] = useState(null);

  // Feature #79 — den fuldt forhåndsviste TMDb-"kladde" der sendes til
  // rediger-boksen. `previewStatus === "ready"` er hvad der faktisk styrer
  // om boksen vises.
  const [previewData, setPreviewData] = useState(null);
  const [previewStatus, setPreviewStatus] = useState("idle");

  useEffect(() => {
    api.attributeOptions().then(setAttributeOptions).catch(() => {});
    api.listTags().then(setAllTags).catch(() => {});
    api.listOwners().then(setAllOwners).catch(() => {});
    api.listLocations().then(setAllLocations).catch(() => {});
    api
      .getSerialNumberConfig()
      .then((cfg) => setSerialPaddingWidth(cfg.padding_width))
      .catch(() => {});
  }, []);

  async function handleDetected(code) {
    setBarcode(code);
    setBarcodeSource(null);
    setManualStatus("idle");
    setScanStatus("looking-up");
    try {
      const result = await api.scanLookup(code);
      setCandidates(result.candidates ?? []);
      setBarcodeSource(result.barcode_source ?? null);
      setScanStatus("ready");
    } catch {
      setScanStatus("error");
    }
  }

  async function submitManualBarcode(event) {
    event.preventDefault();
    const code = manualBarcode.trim();
    if (!code) return;
    await handleDetected(code);
  }

  async function searchManually(event) {
    event.preventDefault();
    if (!manualQuery.trim()) return;

    setBarcode(null);
    setBarcodeSource(null);
    setManualStatus("searching");
    try {
      // Søger både film og TV-serier (feature #49/#50) — samme princip som
      // stregkode-opslaget, som allerede returnerer begge typer samlet.
      const [movieResults, tvResults] = await Promise.all([
        api.tmdbSearch(manualQuery.trim()),
        api.tvTmdbSearch(manualQuery.trim()).catch(() => []),
      ]);
      setCandidates([
        ...movieResults.map((c) => ({ ...c, media_kind: "movie" })),
        ...tvResults,
      ]);
      setScanStatus("ready");
      setManualStatus("ready");
    } catch {
      setManualStatus("error");
    }
  }

  function selectCandidate(candidate) {
    setSelectedCandidate(candidate);
    setSaveStatus("idle");
    setDuplicates([]);
    setExistingTvShow(null);
    setPreviewSeasons([]);
    setSelectedSeasonNumbers([]);
    setGroupStatus("idle");
    setGroupError(null);
    setGroupSavedShowName(null);
    setPreviewData(null);
    setPreviewStatus("idle");
    if (candidate.media_kind !== "tv") {
      api.checkDuplicate(candidate.tmdb_id).then(setDuplicates).catch(() => {});
      return;
    }
    api
      .checkTvDuplicate(candidate.tmdb_id)
      .then((matches) => {
        setDuplicates(matches);
        if (matches.length > 0) {
          // Kun den første eksisterende serie tilbydes som gruppering — jf.
          // Jans bekræftede design (2026-08-02): ét scan grupperes ind i den
          // ene eksisterende post, ikke et valg mellem flere.
          api
            .getTvShow(matches[0].id)
            .then((show) => {
              setExistingTvShow(show);
              const preselect = show.seasons.find((s) => !s.owned) ?? show.seasons[0];
              setSelectedSeasonNumbers(preselect ? [preselect.season_number] : []);
            })
            .catch(() => {});
        } else {
          // Ingen dublet — vis en sæson-vælger til forhåndsvisning, så
          // brugeren kan afkrydse hvilke sæsoner udgaven indeholder inden
          // der springes videre til rediger-boksen (feature #54).
          api.tvTmdbPreview(candidate.tmdb_id).then(setPreviewSeasons).catch(() => {});
        }
      })
      .catch(() => {});
  }

  function toggleSeasonNumber(seasonNumber) {
    setSelectedSeasonNumbers((prev) => toggleValue(prev, seasonNumber));
  }

  function resetFormAfterSave() {
    setSelectedCandidate(null);
    setCandidates([]);
    setBarcode(null);
    setBarcodeSource(null);
    setDuplicates([]);
    setExistingTvShow(null);
    setPreviewSeasons([]);
    setSelectedSeasonNumbers([]);
    setGroupStatus("idle");
    setGroupError(null);
    setPreviewData(null);
    setPreviewStatus("idle");
  }

  async function proceedToEdit() {
    setPreviewStatus("loading");
    try {
      if (selectedCandidate.media_kind === "tv") {
        const preview = await api.tvTmdbFullPreview(selectedCandidate.tmdb_id);
        setPreviewData({
          ...preview,
          barcode,
          barcode_source: barcodeSource,
          ...emptyDraftFields(user, wishlist),
          seasons: previewSeasons.map((season) => ({
            ...season,
            owned: selectedSeasonNumbers.includes(season.season_number),
            episodes: [],
          })),
        });
      } else {
        const preview = await api.movieTmdbPreview(selectedCandidate.tmdb_id);
        setPreviewData({ ...preview, barcode, barcode_source: barcodeSource, ...emptyDraftFields(user, wishlist) });
      }
      setPreviewStatus("ready");
    } catch (err) {
      setPreviewStatus("error");
    }
  }

  async function addSeasonsToExistingShow() {
    if (!existingTvShow || selectedSeasonNumbers.length === 0) return;
    setGroupStatus("saving");
    setGroupError(null);
    try {
      for (const seasonNumber of selectedSeasonNumbers) {
        await api.setSeasonOwned(existingTvShow.id, seasonNumber, true);
      }
      setGroupSavedShowName(existingTvShow.name);
      resetFormAfterSave();
      onSaved?.();
    } catch (err) {
      setGroupStatus("error");
      setGroupError(err.message);
    }
  }

  return (
    <section className="scan-layout">
      <div className="card scan-card">
        <h2>Scan</h2>
        <p className="muted">
          Scan stregkoden på cover'et med kameraet — finder både film og TV-serier.
        </p>
        <BarcodeScanner onDetected={handleDetected} />

        <form className="manual-search-form" onSubmit={submitManualBarcode} style={{ marginTop: 10 }}>
          <input
            value={manualBarcode}
            onChange={(e) => setManualBarcode(e.target.value)}
            placeholder="...eller indtast stregkoden manuelt (UPC/EAN)"
            inputMode="numeric"
          />
          <button type="submit" className="btn btn-primary" disabled={!manualBarcode.trim()}>
            Slå op
          </button>
        </form>

        {barcode && <p className="muted" style={{ marginTop: 10 }}>Scannet stregkode: {barcode}</p>}
        {scanStatus === "looking-up" && <p className="muted">Slår op...</p>}
        {scanStatus === "error" && (
          <div className="banner banner-error">
            Opslag fejlede. Prøv igen, eller søg manuelt på titel nedenfor.
          </div>
        )}
        {scanStatus === "ready" && candidates.length === 0 && !manualQuery && (
          <div className="banner banner-info">Intet match fundet — søg manuelt på titel i stedet.</div>
        )}
      </div>

      <div className="card scan-card">
        <h2>Søg manuelt (TMDb)</h2>
        <form className="manual-search-form" onSubmit={searchManually}>
          <input
            value={manualQuery}
            onChange={(e) => setManualQuery(e.target.value)}
            placeholder="Film- eller serietitel..."
          />
          <button type="submit" className="btn btn-primary">
            Søg
          </button>
        </form>
        {manualStatus === "searching" && <p className="muted" style={{ marginTop: 10 }}>Søger på TMDb...</p>}
        {manualStatus === "error" && (
          <div className="banner banner-error" style={{ marginTop: 10 }}>
            TMDb-søgning fejlede. Tjek at backend har en gyldig TMDB_API_TOKEN.
          </div>
        )}
        {manualStatus === "ready" && candidates.length === 0 && (
          <div className="banner banner-info" style={{ marginTop: 10 }}>Intet matchede din søgning.</div>
        )}
      </div>

      {candidates.length > 0 && (
        <div>
          <h2 style={{ marginBottom: 10 }}>Vælg den rigtige film eller serie</h2>
          <ul className="candidate-grid">
            {candidates.map((candidate) => (
              <li
                key={`${candidate.media_kind}-${candidate.tmdb_id}`}
                className={`candidate-card${selectedCandidate?.tmdb_id === candidate.tmdb_id && selectedCandidate?.media_kind === candidate.media_kind ? " selected" : ""}`}
                onClick={() => selectCandidate(candidate)}
              >
                <div className="candidate-poster">
                  {candidate.poster_url ? (
                    <img src={candidate.poster_url} alt={candidate.title} />
                  ) : (
                    "🎬"
                  )}
                  <span className="candidate-media-kind">
                    {candidate.media_kind === "tv" ? "TV-serie" : "Film"}
                  </span>
                </div>
                <div className="candidate-info">
                  <div className="candidate-title">{candidate.title}</div>
                  <div className="candidate-year">
                    {candidate.year ?? ""}
                    {candidate.rating != null && <> · ★ {candidate.rating.toFixed(1)}</>}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {selectedCandidate && previewStatus !== "ready" && (
        <div className="card review-form">
          <div className="review-header">
            <div className="candidate-poster">
              {selectedCandidate.poster_url ? (
                <img src={selectedCandidate.poster_url} alt={selectedCandidate.title} />
              ) : (
                "🎬"
              )}
            </div>
            <div>
              <h2>{selectedCandidate.title}</h2>
              <p className="muted">{selectedCandidate.year}</p>
            </div>
          </div>

          {duplicates.length > 0 && (
            <div className="banner banner-error">
              Findes allerede: {selectedCandidate.media_kind === "tv" ? "denne serie" : "denne film"} er allerede{" "}
              {duplicates
                .map((d) =>
                  d.is_wishlist
                    ? "på ønskelisten"
                    : `i biblioteket${d.serial_number ? ` (#${d.serial_number})` : ""}`
                )
                .join(" og ")}
              . Du kan stadig tilføje den igen — fx hvis du ejer flere kopier.
            </div>
          )}

          {(existingTvShow?.seasons.length > 0 || previewSeasons.length > 0) && (
            <div className="season-group-panel">
              <h3>
                {existingTvShow ? "Føj til eksisterende serie i stedet" : "Vælg hvilke sæsoner du ejer"}
              </h3>
              <p className="muted" style={{ margin: 0 }}>
                {existingTvShow ? (
                  <>
                    Vælg hvilke sæsoner dette er, så markeres de som ejet på den eksisterende serie "
                    {existingTvShow.name}" — i stedet for at oprette en ny separat post. Sæsoner markeret ✓
                    er allerede ejet.
                  </>
                ) : (
                  "Vælg hvilke sæsoner denne udgave indeholder (fx en boks med flere sæsoner) — de markeres automatisk som ejet, klar til at redigere videre."
                )}
              </p>
              <div className="chip-row">
                {(existingTvShow?.seasons ?? previewSeasons).map((season) => (
                  <Chip
                    key={season.season_number}
                    label={`${season.name ?? `Sæson ${season.season_number}`}${season.owned ? " ✓" : ""}`}
                    active={selectedSeasonNumbers.includes(season.season_number)}
                    onClick={() => toggleSeasonNumber(season.season_number)}
                  />
                ))}
              </div>
              {groupStatus === "error" && (
                <div className="banner banner-error">
                  {groupError ?? "Kunne ikke opdatere serien."}
                </div>
              )}
              {existingTvShow && (
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={addSeasonsToExistingShow}
                  disabled={selectedSeasonNumbers.length === 0 || groupStatus === "saving"}
                >
                  {groupStatus === "saving" ? "Tilføjer..." : "Tilføj sæson(er) til eksisterende serie"}
                </button>
              )}
            </div>
          )}

          {previewStatus === "error" && (
            <div className="banner banner-error">
              Kunne ikke hente fulde detaljer fra TMDb. Prøv igen.
            </div>
          )}

          <div className="review-actions">
            <button type="button" className="btn" onClick={() => setSelectedCandidate(null)}>
              Annullér
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={proceedToEdit}
              disabled={previewStatus === "loading"}
            >
              {previewStatus === "loading"
                ? "Henter detaljer..."
                : existingTvShow
                  ? "Opret som ny separat serie i stedet"
                  : "Fortsæt til redigering"}
            </button>
          </div>
        </div>
      )}

      {previewStatus === "ready" && previewData && selectedCandidate.media_kind === "tv" && (
        <TvShowDetailModal
          show={previewData}
          user={user}
          allTags={allTags}
          allOwners={allOwners}
          allLocations={allLocations}
          attributeOptions={attributeOptions}
          serialPaddingWidth={serialPaddingWidth}
          onClose={resetFormAfterSave}
          onChanged={() => {
            setLastSavedKind("tv");
            setSaveStatus("saved");
            onSaved?.();
          }}
        />
      )}

      {previewStatus === "ready" && previewData && selectedCandidate.media_kind !== "tv" && (
        <MovieDetailModal
          movie={previewData}
          user={user}
          allTags={allTags}
          allOwners={allOwners}
          allLocations={allLocations}
          attributeOptions={attributeOptions}
          serialPaddingWidth={serialPaddingWidth}
          onClose={resetFormAfterSave}
          onChanged={() => {
            setLastSavedKind("movie");
            setSaveStatus("saved");
            onSaved?.();
          }}
          onFilterByPerson={() => {}}
        />
      )}

      {saveStatus === "saved" && (
        <div className="banner banner-info">
          {lastSavedKind === "tv" ? "TV-serie" : "Film"}{" "}
          {wishlist ? "tilføjet til ønskeliste!" : "gemt i biblioteket!"}
        </div>
      )}

      {groupSavedShowName && (
        <div className="banner banner-info">
          Sæson tilføjet til "{groupSavedShowName}"!
        </div>
      )}
    </section>
  );
}
