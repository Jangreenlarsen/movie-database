/**
 * BUGS.md #95 — iOS Safari renders an empty `<input type="date">` completely
 * blank: no "dd-mm-åååå" placeholder digits, no calendar icon, unlike every
 * other engine (desktop Chromium/WebKit/Firefox all show *something*). There
 * is no CSS/feature-detection way to ask "does this browser draw its own
 * empty-date affordance", so this narrowly-scoped UA sniff exists only to
 * decide whether `DateField` needs to draw its own hint on top.
 *
 * iPadOS 13+ reports as a Mac (desktop-class UA) but is still the same
 * WebKit date-input control, so it's caught via the touch-screen check
 * rather than the UA string.
 */
export function isIOS() {
  if (typeof navigator === "undefined") return false;
  return /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
}
