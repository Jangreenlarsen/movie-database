import { useEffect, useState } from "react";
import BarcodeScanner from "../scanner/BarcodeScanner";
import { api } from "../api/client";
import Chip from "./Chip";
import { MovieDetailModal } from "../pages/Library";
import { TvShowDetailModal } from "../pages/TvShows";
import { useT } from "../i18n";
import { posterSrc } from "../utils/posterUrl";
import { duplicateSerialSuffix } from "../utils/serialNumber";
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
    subtitles: null,
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
 *
 * Feature #106 — et klik på en kandidat går direkte til rediger-boksen i
 * stedet for at kræve et scroll ned til et separat "Fortsæt til
 * redigering"-kort. Det gælder ubetinget for film: et evt. dublet-fund
 * ændrer intet ved selve oprettelsen, så det vises som et banner *inde i*
 * rediger-boksen i stedet for at stoppe flowet. For TV-serier er der ét
 * reelt valg der ikke kan springes stiltiende over — findes der allerede en
 * post af samme slags (bibliotek/ønske), skal brugeren selv vælge mellem at
 * tilføje sæson(er) til den eller oprette en ny separat serie, ellers ville
 * hvert scan af en ny sæson-boks stille og roligt oprette sin egen serie
 * (feature #53's oprindelige formål). Det valg vises nu som en rigtig
 * modal-dialog (ingen scroll nødvendig) i stedet for et in-page-kort, og kun
 * når der reelt er noget at vælge — er der intet at gruppere ind i, går
 * flowet lige så direkte til redigering som for film.
 */
export default function MovieLookupForm({ user, wishlist = false, onSaved, mode = "both" }) {
  const t = useT();
  // Feature #124 — `mode` styrer hvilke tilføj-veje der vises. `both` (default)
  // = scan- OG titel-søgnings-kort side om side, som biblioteket altid har haft.
  // `scan`/`manual` = kun det ene kort (ønskelistens to store knapper), så den
  // manuelle titel-søgning ikke forveksles med bibliotekets generelle søgning.
  // Lokal state så scan→titel-fallbacken kan skifte kort uden at forælderen
  // skal remonte panelet; synkroniseres hvis forælderen sender en ny `mode`.
  const [activeMode, setActiveMode] = useState(mode);
  useEffect(() => setActiveMode(mode), [mode]);
  const [barcode, setBarcode] = useState(null);
  const [barcodeSource, setBarcodeSource] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [scanStatus, setScanStatus] = useState("idle");
  // BUGS.md #107 — backendens egen fejltekst (fx "TMDb-nøgle ikke sat"),
  // vist i stedet for den generiske når den findes (regel 16).
  const [scanError, setScanError] = useState(null);
  const [manualBarcode, setManualBarcode] = useState("");
  const [manualQuery, setManualQuery] = useState("");
  const [manualStatus, setManualStatus] = useState("idle");
  const [manualError, setManualError] = useState(null);
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
    order_statuses: [],
    subtitles: [],
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
  const [previewError, setPreviewError] = useState(null);

  // BUGS.md #111 — se den identiske note i Library.jsx.
  const [optionsError, setOptionsError] = useState(null);

  useEffect(() => {
    api
      .attributeOptions()
      .then(setAttributeOptions)
      .catch((err) => setOptionsError(err.message));
    // Bevidst tavse (regel 16): autocomplete-forslag og visningshjælpere.
    // Fejler de, virker siden stadig — felterne har bare ingen forslag, og
    // serienumre vises uden foranstillede nuller.
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
    setScanError(null);
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
    } catch (err) {
      setScanError(err.message);
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
    setManualError(null);
    try {
      // Søger både film og TV-serier (feature #49/#50) — samme princip som
      // stregkode-opslaget, som allerede returnerer begge typer samlet.
      const [movieResults, tvResults] = await Promise.all([
        api.tmdbSearch(manualQuery.trim()),
        // Bevidst tavs: TV-søgningen er et supplement. Er TMDb nede, fejler
        // film-søgningen ovenfor også og viser fejlen; ellers vises blot
        // film-resultaterne.
        api.tvTmdbSearch(manualQuery.trim()).catch(() => []),
      ]);
      setCandidates([
        ...movieResults.map((c) => ({ ...c, media_kind: "movie" })),
        ...tvResults,
      ]);
      setScanStatus("ready");
      setManualStatus("ready");
    } catch (err) {
      setManualError(err.message);
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
      // Dublet-tjekket for film ændrer intet ved selve flowet — det er
      // rent informativt og vises som et banner inde i rediger-boksen — så
      // det behøver ikke afventes før vi går videre (feature #106).
      api.checkDuplicate(candidate.tmdb_id).then(setDuplicates).catch(() => {});
      proceedToEdit(candidate);
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
          // Feature #106 — dette er det ene reelle valg der ikke kan
          // springes stiltiende over: vises som modal så snart
          // `existingTvShow` er sat.
          api
            .getTvShow(groupable.id)
            .then((show) => {
              setExistingTvShow(show);
              const preselect = show.seasons.find((s) => !s.owned) ?? show.seasons[0];
              setSelectedSeasonNumbers(preselect ? [preselect.season_number] : []);
            })
            .catch(() => proceedToEdit(candidate));
        } else {
          // Ingen dublet at gruppere ind i — vis en sæson-vælger til
          // forhåndsvisning, så brugeren kan afkrydse hvilke sæsoner
          // udgaven indeholder inden der springes videre til
          // rediger-boksen (feature #54). Findes der ingen sæsoner at
          // vælge imellem (eller slår opslaget fejl), er der intet valg
          // tilbage, og flowet fortsætter selv direkte til redigering.
          api
            .tvTmdbPreview(candidate.tmdb_id)
            .then((seasons) => {
              setPreviewSeasons(seasons);
              if (seasons.length === 0) proceedToEdit(candidate);
            })
            .catch(() => proceedToEdit(candidate));
        }
      })
      .catch(() => proceedToEdit(candidate));
  }

  function toggleSeasonNumber(seasonNumber) {
    setSelectedSeasonNumbers((prev) => toggleValue(prev, seasonNumber));
  }

  // Feature #106 — går tilbage til kandidat-gitteret uden at rydde selve
  // søge-/scan-resultatet, så et forkert valgt match kan erstattes med et
  // andet uden at starte scanningen/søgningen forfra. `resetFormAfterSave`
  // nedenfor rydder derudover også `candidates` m.fl. — den bruges når hele
  // flowet er afsluttet (gemt, eller sæson(er) tilføjet til en eksisterende
  // serie), ikke når man blot fortryder et enkelt kandidat-valg.
  function backToCandidates() {
    setSelectedCandidate(null);
    setDuplicates([]);
    setExistingTvShow(null);
    setPreviewSeasons([]);
    setSelectedSeasonNumbers([]);
    setGroupStatus("idle");
    setGroupError(null);
    setPreviewData(null);
    setPreviewStatus("idle");
  }

  function resetFormAfterSave() {
    backToCandidates();
    setCandidates([]);
    setBarcode(null);
    setBarcodeSource(null);
    setGuessedTitle(null);
    setManualQuery("");
  }

  async function proceedToEdit(candidateOverride) {
    // `candidateOverride` findes fordi denne funktion nogle gange kaldes
    // synkront lige efter `setSelectedCandidate` i samme funktion (feature
    // #106) — React har på det tidspunkt endnu ikke opdateret
    // `selectedCandidate`, så den nye kandidat skal medbringes eksplicit i
    // stedet for at læses fra state.
    const candidate = candidateOverride ?? selectedCandidate;
    setPreviewStatus("loading");
    try {
      if (candidate.media_kind === "tv") {
        const preview = await api.tvTmdbFullPreview(candidate.tmdb_id);
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
        const preview = await api.movieTmdbPreview(candidate.tmdb_id);
        setPreviewData({ ...preview, barcode, barcode_source: barcodeSource, ...emptyDraftFields(user, wishlist) });
      }
      setPreviewStatus("ready");
    } catch (err) {
      setPreviewError(err.message);
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
      {optionsError && (
        <div className="banner banner-error">
          {t("lib.optionsLoadFailed", { message: optionsError })}
        </div>
      )}
      {activeMode !== "manual" && (
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
          <div className="banner banner-error">{scanError || t("scan.lookupFailed")}</div>
        )}
        {scanStatus === "ready" && candidates.length === 0 && !guessedTitle && (
          <div className="banner banner-info">{t("scan.noMatch")}</div>
        )}
        {scanStatus === "ready" && candidates.length === 0 && guessedTitle && (
          <div className="banner banner-info">
            {t("scan.guessNoTmdbMatch", { guess: guessedTitle })}
          </div>
        )}
        {/* Feature #124 — når scan-kortet vises alene (ønskelistens "Scan
            cover"-knap) og et scan ikke gav et match, er titel-søgningen ikke
            synlig ved siden af; tilbyd derfor et skift dertil. Gættet er
            allerede forudfyldt i manualQuery, så titel-feltet står klar. */}
        {activeMode === "scan" && scanStatus === "ready" && candidates.length === 0 && (
          <button
            type="button"
            className="btn"
            style={{ marginTop: 10 }}
            onClick={() => setActiveMode("manual")}
          >
            {t("scan.tryTitleInstead")}
          </button>
        )}
      </div>
      )}

      {activeMode !== "scan" && (
      <div className="card scan-card">
        <h2>{t("scan.manualHeading")}</h2>
        {activeMode === "manual" && (
          <button
            type="button"
            className="btn"
            style={{ marginBottom: 10 }}
            onClick={() => setActiveMode("scan")}
          >
            {t("scan.tryScanInstead")}
          </button>
        )}
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
            {manualError || t("scan.searchFailed")}
          </div>
        )}
        {manualStatus === "ready" && candidates.length === 0 && (
          <div className="banner banner-info" style={{ marginTop: 10 }}>
            {t("scan.noSearchMatch")}
          </div>
        )}
      </div>
      )}

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
                    <img src={posterSrc(candidate.poster_url, "w185")} alt={candidate.title} />
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

      {/* Feature #106 — resten af "vent"-tilstandene: film der endnu ikke
          har fået deres fulde forhåndsvisning hjem, en TV-kandidat hvis
          dublet-/grupperings-tjek stadig kører, eller en fejl fra selve
          forhåndsvisnings-hentningen. Vises kun når TV-mellemtrinnet
          nedenfor IKKE er relevant — findes der noget at vælge mellem for
          en TV-serie, er det den modal der har ordet. */}
      {selectedCandidate &&
        previewStatus !== "ready" &&
        !(selectedCandidate.media_kind === "tv" && (existingTvShow || previewSeasons.length > 0)) && (
          <div className="card scan-loading-card">
            {previewStatus === "error" ? (
              <>
                <div className="banner banner-error">{previewError || t("scan.detailsFailed")}</div>
                <button type="button" className="btn" onClick={backToCandidates}>
                  {t("scan.backToCandidates")}
                </button>
              </>
            ) : (
              <p className="muted">{t("scan.loadingDetails")}</p>
            )}
          </div>
        )}

      {/* Feature #106 — det ene TV-valg der ikke kan springes over: findes
          der allerede en post af samme slags at gruppere sæson(er) ind i,
          eller er der sæsoner at afkrydse på en helt ny serie, vises det
          som en rigtig modal (ingen scroll nødvendig, dukker op med det
          samme ved klik på kandidaten) i stedet for det tidligere in-page
          "review-form"-kort. */}
      {selectedCandidate &&
        selectedCandidate.media_kind === "tv" &&
        previewStatus !== "ready" &&
        (existingTvShow || previewSeasons.length > 0) && (
          <div className="modal-backdrop" onClick={backToCandidates}>
            <div className="modal-card" onClick={(e) => e.stopPropagation()}>
              <div className="modal-header">
                <div className="modal-poster">
                  {selectedCandidate.poster_url ? (
                    <img src={posterSrc(selectedCandidate.poster_url, "w342")} alt={selectedCandidate.title} />
                  ) : (
                    "📺"
                  )}
                </div>
                <div>
                  <h2>{selectedCandidate.title}</h2>
                  <p className="muted">{selectedCandidate.year}</p>
                </div>
                <button type="button" className="btn modal-close" onClick={backToCandidates}>
                  ✕
                </button>
              </div>

              <div className="modal-body">
                {duplicates.length > 0 && (
                  <div className="banner banner-error">
                    {t("scan.duplicateIntro", {
                      what: t("scan.duplicateShow"),
                      where: duplicates
                        .map((d) =>
                          d.is_wishlist
                            ? t("scan.duplicateOnWishlist")
                            : `${t("scan.duplicateInLibrary")}${duplicateSerialSuffix(d, "tv", serialPaddingWidth)}`
                        )
                        .join(t("scan.duplicateJoin")),
                    })}
                  </div>
                )}

                <div className="season-group-panel">
                  {/* BUGS.md #50 — panelet deles af bibliotekets og
                      ønskelistens tilføj-panel, men talte kun om
                      "ejerskab". Man ejer per definition ikke det man er
                      ved at ønske sig, så teksten følger nu
                      `wishlist`-prop'en. */}
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

                {previewStatus === "error" && (
                  <div className="banner banner-error">{previewError || t("scan.detailsFailed")}</div>
                )}
              </div>

              <div className="modal-footer">
                <button type="button" className="btn" onClick={backToCandidates}>
                  {t("common.cancel")}
                </button>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => proceedToEdit()}
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
          duplicates={duplicates}
          onBackToCandidates={backToCandidates}
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
          duplicates={duplicates}
          onBackToCandidates={backToCandidates}
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
