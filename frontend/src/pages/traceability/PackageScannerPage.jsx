import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import PageHeader from "../../components/ui/PageHeader";
import { useLocale } from "../../context/LocaleContext";
import { parseLabelCode } from "../../utils/labelCode";

export default function PackageScannerPage() {
  const { t } = useLocale();
  const navigate = useNavigate();
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const [manual, setManual] = useState("");
  const [cameraOn, setCameraOn] = useState(false);
  const [cameraError, setCameraError] = useState("");
  const [detectorSupported, setDetectorSupported] = useState(false);

  const openPassport = useCallback(
    (raw) => {
      const code = parseLabelCode(raw);
      if (!code) return;
      navigate(`/packages/${encodeURIComponent(code)}`);
    },
    [navigate]
  );

  useEffect(() => {
    setDetectorSupported(typeof window.BarcodeDetector !== "undefined");
  }, []);

  useEffect(() => {
    if (!cameraOn || !detectorSupported) return undefined;
    let cancelled = false;
    let intervalId;

    const start = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "environment" },
        });
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play();
        }
        const detector = new window.BarcodeDetector({ formats: ["qr_code"] });
        intervalId = setInterval(async () => {
          if (!videoRef.current) return;
          try {
            const codes = await detector.detect(videoRef.current);
            if (codes?.length) {
              openPassport(codes[0].rawValue);
            }
          } catch {
            /* ignore frame errors */
          }
        }, 500);
      } catch (e) {
        setCameraError(e.message || "Camera unavailable");
        setCameraOn(false);
      }
    };

    start();
    return () => {
      cancelled = true;
      if (intervalId) clearInterval(intervalId);
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((tr) => tr.stop());
        streamRef.current = null;
      }
    };
  }, [cameraOn, detectorSupported, openPassport]);

  return (
    <div>
      <PageHeader title={t("traceability.scannerTitle")} subtitle={t("traceability.scannerSubtitle")} />
      <div className="mx-auto max-w-lg space-y-4">
        {detectorSupported ? (
          <div className="overflow-hidden rounded-2xl border bg-black">
            <video ref={videoRef} className="aspect-video w-full object-cover" playsInline muted />
          </div>
        ) : (
          <p className="rounded-2xl border bg-amber-50 px-4 py-3 text-sm text-amber-900">
            {t("traceability.scannerFallback")}
          </p>
        )}
        {cameraError ? <p className="text-sm text-red-600">{cameraError}</p> : null}
        {detectorSupported ? (
          <button
            type="button"
            onClick={() => setCameraOn((v) => !v)}
            className="w-full rounded-2xl bg-black px-4 py-3 text-sm font-semibold text-white"
          >
            {cameraOn ? t("traceability.stopCamera") : t("traceability.startCamera")}
          </button>
        ) : null}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            openPassport(manual);
          }}
          className="flex gap-2"
        >
          <input
            type="text"
            value={manual}
            onChange={(e) => setManual(e.target.value)}
            placeholder="PKG-20260603-00001"
            className="flex-1 rounded-2xl border px-4 py-3 text-sm"
          />
          <button
            type="submit"
            className="rounded-2xl bg-[var(--brand-button)] px-4 py-3 text-sm font-semibold text-white"
          >
            {t("traceability.open")}
          </button>
        </form>
      </div>
    </div>
  );
}
