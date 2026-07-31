import { BrowserMultiFormatReader } from "@zxing/browser";
import { useEffect, useRef, useState } from "react";
import "./BarcodeScanner.css";

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
    const reader = new BrowserMultiFormatReader();
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
