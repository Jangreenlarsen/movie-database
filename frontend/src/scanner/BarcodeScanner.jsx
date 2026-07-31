import { BrowserMultiFormatReader } from "@zxing/browser";
import { useEffect, useRef, useState } from "react";

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
      <video ref={videoRef} style={{ width: "100%", maxWidth: 480 }} muted playsInline />
      {!scanning && <button onClick={startScan}>Start scan</button>}
      {error && <p role="alert">{error}</p>}
    </div>
  );
}
