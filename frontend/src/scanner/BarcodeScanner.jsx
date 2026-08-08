import { BarcodeFormat, BrowserMultiFormatReader } from "@zxing/browser";
import { DecodeHintType } from "@zxing/library";
import { useEffect, useRef, useState } from "react";
import { useT } from "../i18n";
import "./BarcodeScanner.css";

// Restricted to the two formats DVD/Blu-ray covers actually use (see
// CLAUDE.md/MOVIE_API_REFERENCE.md — EAN-13 for EU/DK, UPC-A for US
// releases). Without this, BrowserMultiFormatReader tries every symbology
// zxing supports (QR, Code128, ITF, Codabar, ...) on every frame, which on
// a busy cover with multiple barcodes/graphics can lock onto noise and
// silently return a bogus number for a different symbology entirely —
// producing "no match found" even though the real EAN/UPC was never
// actually misread by the user (BUGS.md #19).
const HINTS = new Map([[DecodeHintType.POSSIBLE_FORMATS, [BarcodeFormat.EAN_13, BarcodeFormat.UPC_A]]]);

// Stopping the camera reliably needs both: (1) the IScannerControls object
// returned by decodeFromVideoDevice() — the *only* real stop API in
// @zxing/browser 0.2.1 (there is no `reader.stopContinuousDecode()`; an
// earlier version of this cleanup called that nonexistent method, which
// threw a TypeError on every unmount and crashed the whole page on iOS
// Safari, requiring a manual reload — BUGS.md #35), and (2) explicitly
// stopping every MediaStream track and clearing `srcObject` on the <video>
// element, since WebKit doesn't always release the hardware compositing
// layer from just `controls.stop()` alone.
function releaseCamera(videoEl) {
  const stream = videoEl?.srcObject;
  if (stream instanceof MediaStream) {
    stream.getTracks().forEach((track) => track.stop());
  }
  if (videoEl) {
    videoEl.srcObject = null;
    videoEl.load();
  }
}

export default function BarcodeScanner({ onDetected }) {
  const t = useT();
  const videoRef = useRef(null);
  const controlsRef = useRef(null);
  const [error, setError] = useState(null);
  const [scanning, setScanning] = useState(false);

  useEffect(() => {
    return () => {
      controlsRef.current?.stop();
      releaseCamera(videoRef.current);
    };
  }, []);

  async function startScan() {
    setError(null);
    setScanning(true);
    const reader = new BrowserMultiFormatReader(HINTS);

    try {
      const controls = await reader.decodeFromVideoDevice(
        undefined,
        videoRef.current,
        (result, err) => {
          if (result) {
            controls.stop();
            releaseCamera(videoRef.current);
            setScanning(false);
            onDetected(result.getText());
          }
        }
      );
      controlsRef.current = controls;
    } catch (err) {
      setError(err instanceof Error ? err.message : t("scanner.cameraError"));
      setScanning(false);
    }
  }

  return (
    <div className="barcode-scanner">
      <div className={`viewfinder${scanning ? " viewfinder-active" : ""}`}>
        <video ref={videoRef} muted playsInline />
        {scanning && (
          <>
            <span className="corner corner-tl" />
            <span className="corner corner-tr" />
            <span className="corner corner-bl" />
            <span className="corner corner-br" />
            <span className="scan-line" />
          </>
        )}
        {!scanning && (
          <div className="viewfinder-placeholder">
            <span>📷</span>
            <p className="muted">Kameraet er slukket</p>
          </div>
        )}
      </div>

      {!scanning && (
        <button type="button" className="btn btn-primary" onClick={startScan}>
          Start scan
        </button>
      )}
      {error && <div className="banner banner-error">{error}</div>}
    </div>
  );
}
