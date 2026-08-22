// Feature #190 (Jan, 2026-08-22: "hvordan sikker vi os også at folk ikke
// sider med cache version af site, kan vi gøre noget sådan at browser altid
// er loadet med nyeste version").
//
// vite-plugin-pwas egen auto-injicerede registrering (nu slået fra i
// vite.config.js, se `injectRegister: false` der) tjekker kun for en ny
// service worker-version ved en rigtig sideindlæsning/navigation — det er
// browserens eget, indbyggede tidspunkt for at genhente `sw.js`. En PWA der
// bliver stående åben i lang tid uden at blive lukket og genåbnet (typisk
// "Føj til hjemmeskærm" på en iPhone, som appen primært bruges fra) rammer
// derfor aldrig det tjek — en ny deployet version kan ligge klar på serveren
// i dagevis uden at nogen browser opdager den.
//
// Løsningen: registrér selv, og lav et EKSPLICIT periodisk
// `registration.update()`-kald ved siden af — vite-plugin-pwas egen
// anbefalede mønster for netop dette problem. `registerType: 'autoUpdate'`
// (uændret i vite.config.js) sørger for at en fundet ny version installeres
// og overtager siden STILLE, uden noget "ny version klar"-prompt — Jans
// eksplicitte valg (automatisk, ubemærket genindlæsning frem for en besked
// brugeren selv skal trykke på).
import { registerSW } from "virtual:pwa-register";

const UPDATE_CHECK_INTERVAL_MS = 20 * 60 * 1000; // 20 minutter

export function registerServiceWorker() {
  registerSW({
    immediate: true,
    onRegisteredSW(swUrl, registration) {
      if (!registration) return;
      setInterval(() => {
        // "connection" findes ikke i alle browsere (fx ældre Safari) — spring
        // blot tjekket over i stedet for at fejle, næste interval prøver igen.
        if ("connection" in navigator && navigator.onLine === false) return;
        registration.update().catch(() => {});
      }, UPDATE_CHECK_INTERVAL_MS);
    },
  });
}
