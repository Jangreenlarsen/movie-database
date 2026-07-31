import { useState } from "react";
import BarcodeScanner from "../scanner/BarcodeScanner";
import { api } from "../api/client";

export default function ScanMovie() {
  const [barcode, setBarcode] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [status, setStatus] = useState("idle");
  const [tags, setTags] = useState("");

  async function handleDetected(code) {
    setBarcode(code);
    setStatus("looking-up");
    try {
      const result = await api.scanLookup(code);
      setCandidates(result.candidates ?? []);
      setStatus("ready");
    } catch {
      setStatus("error");
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
          Opslag fejlede. `/api/scan/lookup` er muligvis ikke implementeret endnu.
        </p>
      )}

      {status === "ready" && candidates.length === 0 && (
        <p>Intet match fundet — søg manuelt på titel i stedet.</p>
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
