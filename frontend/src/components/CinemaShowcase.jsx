import "./CinemaShowcase.css";

// Feature #71 — reklame-/info-sektion for Voldby BIO, brugt både på den
// offentlige /bio-side og den indloggede Voldby BIO-fane. Rent statisk
// indhold (ingen API-kald) — billederne ligger i frontend/public/cinema/.
const PHOTOS = [
  { src: "/cinema/voldbyBIO-1-front.jpg", alt: "Lærred med surround-højttalere og biografstole" },
  { src: "/cinema/voldbyBIO-3.jpg", alt: "Højttaler monteret i loftet" },
  { src: "/cinema/voldbyBIO-2-back.jpg", alt: "Biografstole fordelt på flere niveauer" },
];

export default function CinemaShowcase() {
  return (
    <div className="cinema-showcase">
      <div className="cinema-showcase-photos">
        {PHOTOS.map((photo) => (
          <div key={photo.src} className="cinema-showcase-photo">
            <img
              src={photo.src}
              alt={photo.alt}
              loading="lazy"
              onError={(e) => {
                e.currentTarget.parentElement.style.display = "none";
              }}
            />
          </div>
        ))}
      </div>

      <div className="cinema-showcase-info">
        <div>
          <h3>Rummet</h3>
          <p>
            14 siddepladser fordelt på 3 niveauer i et rum på 30 m². Rummet er akustisk
            behandlet, så der ikke opstår stående lydbølger — alle flader er dæmpet og
            spredt-bygget.
          </p>
        </div>

        <div>
          <h3>Billede</h3>
          <p>Hisense 100" 4K UHD Mini-LED TV (100U7KQ).</p>
        </div>

        <div>
          <h3>Lyd</h3>
          <p>
            9.2.6 surround, styret af en Anthem AVM 70 sound processor.
          </p>
          <ul>
            <li>Klasse AB, 7×300W til de primære højttalere</li>
            <li>Klasse D (Rotel), 8×100W til alle sekundære højttalere</li>
            <li>Klasse AB, 500W til en 21" bas-subwoofer</li>
            <li>Klasse D, 4kW til en 15" LFE-subwoofer (2,5kW)</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
