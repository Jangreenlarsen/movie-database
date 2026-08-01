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
      const results = await api.tmdbSearch(manualQuery.trim());
      setCandidates(results);
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
    api.checkDuplicate(candidate.tmdb_id).then(setDuplicates).catch(() => {});
  }

  async function saveMovie() {
    setSaveStatus("saving");
    setSaveError(null);
    try {
      await api.createMovie({
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
      onSaved?.();
    } catch (err) {
      setSaveStatus("error");
      setSaveError(err.message);
    }
  }

  return (
    <section className="scan-layout">
      <div className="card scan-card">
        <h2>Scan film</h2>
        <p className="muted">Scan stregkoden på cover'et med kameraet.</p>
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
            placeholder="Filmtitel..."
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
          <div className="banner banner-info" style={{ marginTop: 10 }}>Ingen film matchede din søgning.</div>
        )}
      </div>

      {candidates.length > 0 && (
        <div>
          <h2 style={{ marginBottom: 10 }}>Vælg den rigtige film</h2>
          <ul className="candidate-grid">
            {candidates.map((candidate) => (
              <li
                key={candidate.tmdb_id}
                className={`candidate-card${selectedCandidate?.tmdb_id === candidate.tmdb_id ? " selected" : ""}`}
                onClick={() => selectCandidate(candidate)}
              >
                <div className="candidate-poster">
                  {candidate.poster_url ? (
                    <img src={candidate.poster_url} alt={candidate.title} />
                  ) : (
                    "🎬"
                  )}
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
              Findes allerede: denne film er allerede{" "}
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
                  placeholder="Hvem ejer filmen..."
                  style={{ width: "100%" }}
                />
              </div>
            </>
          )}

          {saveStatus === "error" && (
            <div className="banner banner-error">
              {saveError ?? "Kunne ikke gemme filmen. Prøv igen."}
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
              {saveStatus === "saving" ? "Gemmer..." : wishlist ? "Tilføj til ønskeliste" : "Gem film"}
            </button>
          </div>
        </div>
      )}

      {saveStatus === "saved" && (
        <div className="banner banner-info">
          {wishlist ? "Film tilføjet til ønskeliste!" : "Film gemt i biblioteket!"}
        </div>
      )}
    </section>
  );
}
