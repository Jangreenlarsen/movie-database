import { useEffect, useState } from "react";
import BarcodeScanner from "../scanner/BarcodeScanner";
import { api } from "../api/client";
import Chip from "./Chip";
import { MovieDetailModal } from "../pages/Library";
import { TvShowDetailModal } from "../pages/TvShows";
import { useT } from "../i18n";
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
 *
 * `onSaved(kind)` kaldes med `"movie"` eller `"tv"` — søgningen rammer begge
 * TMDb-databaser, så den der viser formularen kan ikke selv vide hvilken
 * collection resultatet endte i. Uden det kunne en TV-serie gemt fra
 * ønskelisten/filmbiblioteket se ud som om den forsvandt (BUGS.md #47).
 */
export default function MovieLookupForm({ user, wishlist = false, onSaved }) {
  const t = useT();
  const [barcode, setBarcode] = useState(null);
  const [barcodeSource, setBarcodeSource] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [scanStatus, setScanStatus] = useState("idle");
  const [manualBarcode, setManualBarcode] = useState("");
  const [manualQuery, setManualQuery] = useState("");
  const [manualStatus, setManualStatus] = useState("idle");
  // Titel-gættet fra stregkode-opslaget (feature #81) — vist til brugeren
  // som en redigerbar tekst, fordi kilderne (især EAN-Search.org) nogle
  // gange returnerer let korrupt eller støjfyldt tekst (fx "rmageddon" uden
  // det første "A"), som ingen automatisk oprydning kan gætte sig til at
  // rette. `manualQuery` forudfyldes med gættet, så brugeren kan se og rette
  // det direkte i "Søg manuelt"-feltet i stedet for at skulle skrive hele
  // titlen fra bunden.
  const [guessedTitle, setGuessedTitle] = useState(null);

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
      setGuessedTitle(result.guessed_title ?? null);
      // Forudfylder "Søg manuelt"-feltet med gættet, uanset om det gav
      // kandidater eller ej — brugeren kan rette teksten (fx en manglende
      // bogstav fra kilden) og trykke "Søg" for at prøve igen.
      setManualQuery(result.guessed_title ?? "");
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
    setGuessedTitle(null);
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
        // Kun den første eksisterende serie tilbydes som gruppering — jf.
        // Jans bekræftede design (2026-08-02): ét scan grupperes ind i den
        // ene eksisterende post, ikke et valg mellem flere. Den skal dog
        // være af samme slags som det vi er ved at oprette: markerer man
        // sæsoner som ejet på et *ønske* mens man står i biblioteket (eller
        // omvendt), lander de i en liste man ikke kigger på — samme klasse
        // "hvor blev den af" som BUGS.md #47. Findes der kun en post af den
        // anden slags, oprettes en ny post i stedet; dublet-banneret
        // fortæller uændret at den anden findes.
        const groupable = matches.find((match) => match.is_wishlist === wishlist);
        if (groupable) {
          api
            .getTvShow(groupable.id)
            .then((show) => {
              setExistingTvShow(show);
              const preselect = show.seasons.find((s) => !s.owned) ?? show.seasons[0];
              setSelectedSeasonNumbers(preselect ? [preselect.season_number] : []);
            })
            .catch(() => {});
        } else {
          // Ingen dublet at gruppere ind i — vis en sæson-vælger til
          // forhåndsvisning, så
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
    setGuessedTitle(null);
    setManualQuery("");
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
      onSaved?.("tv");
    } catch (err) {
      setGroupStatus("error");
      setGroupError(err.message);
    }
  }

  return (
    <section className="scan-layout">
      <div className="card scan-card">
        <h2>{t("scan.heading")}</h2>
        <p className="muted">{t("scan.description")}</p>
        <BarcodeScanner onDetected={handleDetected} />

        <form className="manual-search-form" onSubmit={submitManualBarcode} style={{ marginTop: 10 }}>
          <input
            value={manualBarcode}
            onChange={(e) => setManualBarcode(e.target.value)}
            placeholder={t("scan.manualBarcodePlaceholder")}
            inputMode="numeric"
          />
          <button type="submit" className="btn btn-primary" disabled={!manualBarcode.trim()}>
            {t("scan.lookUp")}
          </button>
        </form>

        {barcode && (
          <p className="muted" style={{ marginTop: 10 }}>
            {t("scan.scannedBarcode", { barcode })}
          </p>
        )}
        {scanStatus === "looking-up" && <p className="muted">{t("scan.lookingUp")}</p>}
        {scanStatus === "error" && (
          <div className="banner banner-error">{t("scan.lookupFailed")}</div>
        )}
        {scanStatus === "ready" && candidates.length === 0 && !guessedTitle && (
          <div className="banner banner-info">{t("scan.noMatch")}</div>
        )}
        {scanStatus === "ready" && candidates.length === 0 && guessedTitle && (
          <div className="banner banner-info">
            {t("scan.guessNoTmdbMatch", { guess: guessedTitle })}
          </div>
        )}
      </div>

      <div className="card scan-card">
        <h2>{t("scan.manualHeading")}</h2>
        {guessedTitle && (
          <p className="muted" style={{ marginTop: 0 }}>
            {t("scan.prefilledHint")}
          </p>
        )}
        <form className="manual-search-form" onSubmit={searchManually}>
          <input
            value={manualQuery}
            onChange={(e) => setManualQuery(e.target.value)}
            placeholder={t("scan.titlePlaceholder")}
          />
          <button type="submit" className="btn btn-primary">
            {t("scan.search")}
          </button>
        </form>
        {manualStatus === "searching" && (
          <p className="muted" style={{ marginTop: 10 }}>
            {t("scan.searching")}
          </p>
        )}
        {manualStatus === "error" && (
          <div className="banner banner-error" style={{ marginTop: 10 }}>
            {t("scan.searchFailed")}
          </div>
        )}
        {manualStatus === "ready" && candidates.length === 0 && (
          <div className="banner banner-info" style={{ marginTop: 10 }}>
            {t("scan.noSearchMatch")}
          </div>
        )}
      </div>

      {candidates.length > 0 && (
        <div>
          <h2 style={{ marginBottom: 10 }}>{t("scan.chooseCandidate")}</h2>
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
                    {t(candidate.media_kind === "tv" ? "scan.kindTv" : "scan.kindMovie")}
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
              {t("scan.duplicateIntro", {
                what: t(
                  selectedCandidate.media_kind === "tv" ? "scan.duplicateShow" : "scan.duplicateMovie"
                ),
                where: duplicates
                  .map((d) =>
                    d.is_wishlist
                      ? t("scan.duplicateOnWishlist")
                      : `${t("scan.duplicateInLibrary")}${d.serial_number ? ` (#${d.serial_number})` : ""}`
                  )
                  .join(t("scan.duplicateJoin")),
              })}
            </div>
          )}

          {(existingTvShow?.seasons.length > 0 || previewSeasons.length > 0) && (
            <div className="season-group-panel">
              {/* BUGS.md #50 — panelet deles af bibliotekets og ønskelistens
                  tilføj-panel, men talte kun om "ejerskab". Man ejer per
                  definition ikke det man er ved at ønske sig, så teksten
                  følger nu `wishlist`-prop'en. */}
              <h3>
                {t(
                  existingTvShow
                    ? wishlist
                      ? "scan.seasonsAddToWish"
                      : "scan.seasonsAddToShow"
                    : wishlist
                      ? "scan.seasonsPickWished"
                      : "scan.seasonsPickOwned"
                )}
              </h3>
              <p className="muted" style={{ margin: 0 }}>
                {existingTvShow
                  ? t(
                      wishlist ? "scan.seasonsExistingWish" : "scan.seasonsExistingShow",
                      { name: existingTvShow.name }
                    )
                  : t(wishlist ? "scan.seasonsNewWish" : "scan.seasonsNewShow")}
              </p>
              <div className="chip-row">
                {(existingTvShow?.seasons ?? previewSeasons).map((season) => (
                  <Chip
                    key={season.season_number}
                    label={`${
                      season.name ?? t("scan.seasonFallback", { number: season.season_number })
                    }${season.owned ? " ✓" : ""}`}
                    active={selectedSeasonNumbers.includes(season.season_number)}
                    onClick={() => toggleSeasonNumber(season.season_number)}
                  />
                ))}
              </div>
              {groupStatus === "error" && (
                <div className="banner banner-error">
                  {groupError ?? t("scan.seasonUpdateFailed")}
                </div>
              )}
              {existingTvShow && (
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={addSeasonsToExistingShow}
                  disabled={selectedSeasonNumbers.length === 0 || groupStatus === "saving"}
                >
                  {t(
                    groupStatus === "saving"
                      ? "scan.addingSeasons"
                      : wishlist
                        ? "scan.addSeasonsToWish"
                        : "scan.addSeasonsToShow"
                  )}
                </button>
              )}
            </div>
          )}

          {previewStatus === "error" && (
            <div className="banner banner-error">{t("scan.detailsFailed")}</div>
          )}

          <div className="review-actions">
            <button type="button" className="btn" onClick={() => setSelectedCandidate(null)}>
              {t("common.cancel")}
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={proceedToEdit}
              disabled={previewStatus === "loading"}
            >
              {t(
                previewStatus === "loading"
                  ? "scan.loadingDetails"
                  : existingTvShow
                    ? wishlist
                      ? "scan.createSeparateWish"
                      : "scan.createSeparateShow"
                    : "scan.continueToEdit"
              )}
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
            onSaved?.("tv");
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
            onSaved?.("movie");
          }}
          onFilterByPerson={() => {}}
        />
      )}

      {saveStatus === "saved" && (
        <div className="banner banner-info">
          {t(wishlist ? "scan.savedToWishlist" : "scan.savedToLibrary", {
            kind: t(lastSavedKind === "tv" ? "scan.kindTv" : "scan.kindMovie"),
          })}
        </div>
      )}

      {groupSavedShowName && (
        <div className="banner banner-info">
          {t("scan.seasonAdded", { name: groupSavedShowName })}
        </div>
      )}
    </section>
  );
}
