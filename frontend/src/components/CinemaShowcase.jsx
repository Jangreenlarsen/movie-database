import { useT } from "../i18n";
import "./CinemaShowcase.css";

// Feature #71 — reklame-/info-sektion for Voldby BIO, brugt både på den
// offentlige /bio-side og den indloggede Voldby BIO-fane. Rent statisk
// indhold (ingen API-kald) — billederne ligger i frontend/public/cinema/.
const PHOTOS = [
  { src: "/cinema/voldbyBIO-1-front.jpg", altKey: "showcase.photo1Alt" },
  { src: "/cinema/voldbyBIO-3.jpg", altKey: "showcase.photo2Alt" },
  { src: "/cinema/voldbyBIO-2-back.jpg", altKey: "showcase.photo3Alt" },
];

export default function CinemaShowcase() {
  const t = useT();
  return (
    <div className="cinema-showcase">
      <div className="cinema-showcase-photos">
        {PHOTOS.map((photo) => (
          <div key={photo.src} className="cinema-showcase-photo">
            <img
              src={photo.src}
              alt={t(photo.altKey)}
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
          <h3>{t("showcase.roomHeading")}</h3>
          <p>{t("showcase.roomText")}</p>
        </div>

        <div>
          <h3>{t("showcase.pictureHeading")}</h3>
          <p>{t("showcase.pictureText")}</p>
        </div>

        <div>
          <h3>{t("showcase.soundHeading")}</h3>
          <p>{t("showcase.soundText")}</p>
          <ul>
            <li>{t("showcase.amp1")}</li>
            <li>{t("showcase.amp2")}</li>
            <li>{t("showcase.amp3")}</li>
            <li>{t("showcase.amp4")}</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
