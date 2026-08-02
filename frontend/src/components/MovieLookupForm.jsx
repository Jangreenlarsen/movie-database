import { useEffect, useState } from "react";
import BarcodeScanner from "../scanner/BarcodeScanner";
import { api } from "../api/client";
import Chip from "./Chip";
import "./MovieLookupForm.css";

function toggleValue(list, value) {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}

/**
 * Barcode-scan + manual TMDb-search + confirm-and-save flow. Shared by the
 * "Scan film" page (wishlist=false) and the "Ønsker" section's own add-panel
 * (wishlist=true) — same lookup method and data source in both places, only
 * the save target differs (jf. Jans ønske om samme metode/data opslag).
 */
export default function MovieLookupForm({ user, wishlist = false, onSaved }) {
  const [barcode, setBarcode] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [scanStatus, setScanStatus] = useState("idle");
  const [manualBarcode, setManualBarcode] = useState("");
  const [manualQuery, setManualQuery] = useState("");
  const [manualStatus, setManualStatus] = useState("idle");

  const [selectedCandidate, setSelectedCandidate] = useState(null);
  const [tagsInput, setTagsInput] = useState("");
  const [format, setFormat] = useState("");
  const [audioTypes, setAudioTypes] = useState([]);
  const [mediaType, setMediaType] = useState("");
  const [location, setLocation] = useState("");
  const [owner, setOwner] = useState(user?.username ?? "");
  const [attributeOptions, setAttributeOptions] = useState({
    formats: [],
    audio_types: [],
    media_types: [],
  });
  const [saveStatus, setSaveStatus] = useState("idle");
  const [saveError, setSaveError] = useState(null);
  const [duplicates, setDuplicates] = useState([]);
  const [lastSavedKind, setLastSavedKind] = useState("movie");

  // Sæson-gruppering (feature #53): når en scannet/søgt TV-serie allerede
  // findes, kan brugeren i stedet markere en sæson som ejet på den
  // eksisterende serie — undgår at hver ny sæson-boks (fx "The Americans
  // Season 2") opretter sin egen separate serie-post.
  const [existingTvShow, setExistingTvShow] = useState(null);
  const [selectedSeasonNumber, setSelectedSeasonNumber] = useState(null);
  const [groupStatus, setGroupStatus] = useState("idle");
  const [groupError, setGroupError] = useState(null);
  const [groupSavedShowName, setGroupSavedShowName] = useState(null);

  useEffect(() => {
    api.attributeOptions().then(setAttributeOptions).catch(() => {});
  }, []);

  async function handleDetected(code) {
    setBarcode(code);
    setManualStatus("idle");
    setScanStatus("looking-up");
    try {
      const result = await api.scanLookup(code);
      setCandidates(result.candidates ?? []);
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
    setSelectedSeasonNumber(null);
    setGroupStatus("idle");
    setGroupError(null);
    setGroupSavedShowName(null);
    const checkDuplicate =
      candidate.media_kind === "tv" ? api.checkTvDuplicate : api.checkDuplicate;
    checkDuplicate(candidate.tmdb_id)
      .then((matches) => {
        setDuplicates(matches);
        if (candidate.media_kind !== "tv" || matches.length === 0) return;
        // Kun den første eksisterende serie tilbydes som gruppering — jf.
        // Jans bekræftede design (2026-08-02): ét scan grupperes ind i den
        // ene eksisterende post, ikke et valg mellem flere.
        api
          .getTvShow(matches[0].id)
          .then((show) => {
            setExistingTvShow(show);
            const preselect = show.seasons.find((s) => !s.owned) ?? show.seasons[0];
            setSelectedSeasonNumber(preselect?.season_number ?? null);
          })
          .catch(() => {});
      })
      .catch(() => {});
  }

  function resetFormAfterSave() {
    setSelectedCandidate(null);
    setCandidates([]);
    setTagsInput("");
    setFormat("");
    setAudioTypes([]);
    setMediaType("");
    setLocation("");
    setOwner(user?.username ?? "");
    setBarcode(null);
    setDuplicates([]);
    setExistingTvShow(null);
    setSelectedSeasonNumber(null);
    setGroupStatus("idle");
    setGroupError(null);
  }

  async function saveMovie() {
    setSaveStatus("saving");
    setSaveError(null);
    const isTv = selectedCandidate.media_kind === "tv";
    try {
      const create = isTv ? api.createTvShow : api.createMovie;
      await create({
        tmdb_id: selectedCandidate.tmdb_id,
        barcode,
        tags: tagsInput.split(",").map((t) => t.trim()).filter(Boolean),
        format: format || null,
        audio_types: audioTypes,
        media_type: mediaType || null,
        location: location.trim() || null,
        owner: owner.trim() || null,
        is_wishlist: wishlist,
      });
      setSaveStatus("saved");
      setLastSavedKind(selectedCandidate.media_kind ?? "movie");
      resetFormAfterSave();
      onSaved?.();
    } catch (err) {
      setSaveStatus("error");
      setSaveError(err.message);
    }
  }

  async function addSeasonToExistingShow() {
    if (!existingTvShow || selectedSeasonNumber == null) return;
    setGroupStatus("saving");
    setGroupError(null);
    try {
      await api.setSeasonOwned(existingTvShow.id, selectedSeasonNumber, true);
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

      {selectedCandidate && (
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

          {existingTvShow && existingTvShow.seasons.length > 0 && (
            <div className="season-group-panel">
              <h3>Føj til eksisterende serie i stedet</h3>
              <p className="muted" style={{ margin: 0 }}>
                Vælg hvilken sæson dette er, så markeres den som ejet på den eksisterende serie "
                {existingTvShow.name}" — i stedet for at oprette en ny separat post. Sæsoner markeret ✓ er
                allerede ejet.
              </p>
              <div className="chip-row">
                {existingTvShow.seasons.map((season) => (
                  <Chip
                    key={season.season_number}
                    label={`${season.name ?? `Sæson ${season.season_number}`}${season.owned ? " ✓" : ""}`}
                    active={selectedSeasonNumber === season.season_number}
                    onClick={() => setSelectedSeasonNumber(season.season_number)}
                  />
                ))}
              </div>
              {groupStatus === "error" && (
                <div className="banner banner-error">
                  {groupError ?? "Kunne ikke opdatere serien."}
                </div>
              )}
              <button
                type="button"
                className="btn btn-primary"
                onClick={addSeasonToExistingShow}
                disabled={selectedSeasonNumber == null || groupStatus === "saving"}
              >
                {groupStatus === "saving" ? "Tilføjer..." : "Tilføj sæson til eksisterende serie"}
              </button>
            </div>
          )}

          <div>
            <label className="field-label" htmlFor="tags-input">
              Tags (kommasepareret)
            </label>
            <input
              id="tags-input"
              value={tagsInput}
              onChange={(e) => setTagsInput(e.target.value)}
              placeholder="Julefilm, Set med Anna, 4K..."
              style={{ width: "100%" }}
            />
          </div>

          <div>
            <span className="field-label">Format</span>
            <div className="chip-row">
              {attributeOptions.formats.map((f) => (
                <Chip key={f} label={f} active={format === f} onClick={() => setFormat(format === f ? "" : f)} />
              ))}
            </div>
          </div>

          <div>
            <span className="field-label">Medietype</span>
            <div className="chip-row">
              {attributeOptions.media_types.map((m) => (
                <Chip
                  key={m}
                  label={m}
                  active={mediaType === m}
                  onClick={() => setMediaType(mediaType === m ? "" : m)}
                />
              ))}
            </div>
          </div>

          <div>
            <span className="field-label">Lyd-type</span>
            <div className="chip-row">
              {attributeOptions.audio_types.map((audioType) => (
                <Chip
                  key={audioType}
                  label={audioType}
                  active={audioTypes.includes(audioType)}
                  onClick={() => setAudioTypes((prev) => toggleValue(prev, audioType))}
                />
              ))}
            </div>
          </div>

          {!wishlist && (
            <>
              <div>
                <label className="field-label" htmlFor="location-input">
                  Lokation
                </label>
                <input
                  id="location-input"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  placeholder="Stue, reol 2..."
                  style={{ width: "100%" }}
                />
              </div>

              <div>
                <label className="field-label" htmlFor="owner-input">
                  Ejer
                </label>
                <input
                  id="owner-input"
                  value={owner}
                  onChange={(e) => setOwner(e.target.value)}
                  placeholder="Hvem ejer den..."
                  style={{ width: "100%" }}
                />
              </div>
            </>
          )}

          {saveStatus === "error" && (
            <div className="banner banner-error">
              {saveError ?? "Kunne ikke gemme. Prøv igen."}
            </div>
          )}

          <div className="review-actions">
            <button type="button" className="btn" onClick={() => setSelectedCandidate(null)}>
              Annullér
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={saveMovie}
              disabled={saveStatus === "saving"}
            >
              {saveStatus === "saving"
                ? "Gemmer..."
                : wishlist
                  ? "Tilføj til ønskeliste"
                  : existingTvShow
                    ? "Opret som ny separat serie"
                    : "Gem"}
            </button>
          </div>
        </div>
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
