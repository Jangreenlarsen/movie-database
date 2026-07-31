import { useState } from "react";
import BarcodeScanner from "../scanner/BarcodeScanner";
import { api } from "../api/client";

export default function ScanMovie() {
  const [barcode, setBarcode] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [status, setStatus] = useState("idle");
  const [tags, setTags] = useState("");
  const [manualQuery, setManualQuery] = useState("");
  const [manualStatus, setManualStatus] = useState("idle");

  async function handleDetected(code) {
    setBarcode(code);
    setManualStatus("idle");
    setStatus("looking-up");
    try {
      const result = await api.scanLookup(code);
      setCandidates(result.candidates ?? []);
      setStatus("ready");
    } catch {
      setStatus("error");
    }
  }

  async function searchManually(event) {
    event.preventDefault();
    if (!manualQuery.trim()) return;

    setBarcode(null);
    setManualStatus("searching");
    try {
      const results = await api.tmdbSearch(manualQuery.trim());
      setCandidates(results);
      setStatus("ready");
      setManualStatus("ready");
    } catch {
      setManualStatus("error");
    }
  }

  async function confirmCandidate(candidate) {
    await api.createMovie({
      tmdb_id: candidate.tmdb_id,
      barcode,
      tags: tags
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean),
    });
    setStatus("saved");
  }

  return (
    <section>
      <h1>Scan film</h1>
      <BarcodeScanner onDetected={handleDetected} />

      {barcode && <p>Scannet stregkode: {barcode}</p>}
      {status === "looking-up" && <p>Slår op...</p>}
      {status === "error" && (
        <p role="alert">
          Opslag fejlede. Prøv igen, eller søg manuelt på titel i stedet.
        </p>
      )}

      {status === "ready" && candidates.length === 0 && (
        <p>Intet match fundet — søg manuelt på titel i stedet.</p>
      )}

      <form onSubmit={searchManually}>
        <label>
          Søg manuelt på titel (TMDb):
          <input
            value={manualQuery}
            onChange={(e) => setManualQuery(e.target.value)}
            placeholder="Filmtitel..."
          />
        </label>
        <button type="submit">Søg</button>
      </form>
      {manualStatus === "searching" && <p>Søger på TMDb...</p>}
      {manualStatus === "error" && (
        <p role="alert">
          TMDb-søgning fejlede. Tjek at backend har en gyldig TMDB_API_TOKEN
          konfigureret (se MOVIE_API_REFERENCE.md).
        </p>
      )}
      {manualStatus === "ready" && candidates.length === 0 && (
        <p>Ingen film matchede din søgning.</p>
      )}

      {status === "ready" && candidates.length > 0 && (
        <div>
          <label>
            Tags (kommasepareret):
            <input value={tags} onChange={(e) => setTags(e.target.value)} />
          </label>
          <ul>
            {candidates.map((candidate) => (
              <li key={candidate.tmdb_id}>
                {candidate.poster_url && (
                  <img src={candidate.poster_url} alt={candidate.title} />
                )}
                {candidate.title} ({candidate.year})
                <button onClick={() => confirmCandidate(candidate)}>Bekræft</button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {status === "saved" && <p>Film gemt!</p>}
    </section>
  );
}
