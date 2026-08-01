import { BarcodeFormat, BrowserMultiFormatReader } from "@zxing/browser";
import { DecodeHintType } from "@zxing/library";
import { useEffect, useRef, useState } from "react";
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

export default function BarcodeScanner({ onDetected }) {
  const videoRef = useRef(null);
  const readerRef = useRef(null);
  const [error, setError] = useState(null);
  const [scanning, setScanning] = useState(false);

  useEffect(() => {
    return () => {
      readerRef.current?.stopContinuousDecode();
    };
  }, []);

  async function startScan() {
    setError(null);
    setScanning(true);
    const reader = new BrowserMultiFormatReader(HINTS);
    readerRef.current = reader;

    try {
      const controls = await reader.decodeFromVideoDevice(
        undefined,
        videoRef.current,
        (result, err) => {
          if (result) {
            controls.stop();
            setScanning(false);
            onDetected(result.getText());
          }
        }
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kunne ikke tilgå kameraet");
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
