"use client";

import { useEffect, useRef, useState } from "react";
import {
  Scanner,
  type IDetectedBarcode,
  type IScannerHandle,
} from "@yudiel/react-qr-scanner";
import { Camera, Keyboard } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onScan: (code: string) => void;
};

/** Product SKUs / RMS codes — not QR-only. */
const BARCODE_FORMATS = [
  "code_128",
  "code_39",
  "code_93",
  "ean_13",
  "ean_8",
  "upc_a",
  "upc_e",
  "itf",
  "codabar",
  "qr_code",
] as const;

function isSecureCameraContext() {
  if (typeof window === "undefined") return false;
  return window.isSecureContext;
}

/** Rear cameras should match reality; front/webcam previews feel natural when mirrored. */
function shouldMirrorPreview(stream: MediaStream | null): boolean {
  const facing = stream?.getVideoTracks()[0]?.getSettings()?.facingMode;
  return facing !== "environment";
}

export function BarcodeScanModal({ open, onOpenChange, onScan }: Props) {
  const scannerRef = useRef<IScannerHandle>(null);
  const [manual, setManual] = useState("");
  const [mode, setMode] = useState<"camera" | "manual">("camera");
  const [error, setError] = useState<string | null>(null);
  const [mirror, setMirror] = useState(true);
  const secure = isSecureCameraContext();

  useEffect(() => {
    if (!open) {
      setManual("");
      setError(null);
      setMode("camera");
      setMirror(true);
      return;
    }
    // Camera APIs are blocked on http://LAN-IP — fall back to manual / BT gun.
    if (!secure) {
      setMode("manual");
      setError(
        "Camera needs HTTPS. Open the https:// LAN link from the launcher, or use Manual / a Bluetooth barcode gun.",
      );
    }
  }, [open, secure]);

  useEffect(() => {
    if (!open || mode !== "camera" || !secure) return;

    let cancelled = false;
    const syncMirror = () => {
      if (cancelled) return;
      const stream = scannerRef.current?.getStream() ?? null;
      if (!stream) return false;
      setMirror(shouldMirrorPreview(stream));
      return true;
    };

    if (syncMirror()) return;

    const timer = window.setInterval(() => {
      if (syncMirror()) window.clearInterval(timer);
    }, 200);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [open, mode, secure]);

  function submitCode(code: string) {
    const trimmed = code.trim();
    if (!trimmed) return;
    onScan(trimmed);
    onOpenChange(false);
  }

  function handleCameraScan(results: IDetectedBarcode[]) {
    const text = results[0]?.rawValue?.trim();
    if (text) submitCode(text);
  }

  function handleCameraError(err: unknown) {
    const kind =
      err && typeof err === "object" && "kind" in err
        ? String((err as { kind: string }).kind)
        : "";
    const message =
      err && typeof err === "object" && "message" in err
        ? String((err as { message: string }).message)
        : err instanceof Error
          ? err.message
          : typeof err === "string"
            ? err
            : "Camera unavailable";

    if (kind === "insecure-context" || /secure|insecure/i.test(message)) {
      setError(
        "Camera blocked: use the https:// address (not http://) on this tablet, or Manual entry.",
      );
      setMode("manual");
      return;
    }
    if (kind === "permission-denied" || /permission|notallowed/i.test(message)) {
      setError(
        "Camera permission denied — allow camera for this site, or use Manual.",
      );
      return;
    }
    if (kind === "no-camera") {
      setError("No camera found — use Manual / Bluetooth barcode gun.");
      setMode("manual");
      return;
    }
    setError(`${message} — try Manual entry or a Bluetooth barcode gun.`);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Scan or enter barcode</DialogTitle>
        </DialogHeader>

        <div className="grid grid-cols-2 gap-2">
          <Button
            type="button"
            variant={mode === "camera" ? "default" : "outline"}
            className="min-h-11 gap-2"
            disabled={!secure}
            onClick={() => {
              setError(null);
              setMode("camera");
            }}
          >
            <Camera className="size-4" /> Camera
          </Button>
          <Button
            type="button"
            variant={mode === "manual" ? "default" : "outline"}
            className="min-h-11 gap-2"
            onClick={() => setMode("manual")}
          >
            <Keyboard className="size-4" /> Manual / gun
          </Button>
        </div>

        {mode === "camera" && secure ? (
          <div className="space-y-2">
            <div className="overflow-hidden rounded-xl border bg-black">
              <Scanner
                ref={scannerRef}
                formats={[...BARCODE_FORMATS]}
                constraints={{
                  facingMode: { ideal: "environment" },
                }}
                components={{ torch: true, finder: true }}
                scanDelay={400}
                onScan={handleCameraScan}
                onError={handleCameraError}
                styles={{
                  container: { width: "100%", minHeight: 240 },
                  // Preview-only flip — detection still reads the raw frames.
                  video: mirror
                    ? { transform: "scaleX(-1)" }
                    : { transform: "none" },
                }}
              />
            </div>
            {error ? (
              <p className="text-sm text-destructive">{error}</p>
            ) : (
              <p className="text-xs text-muted-foreground">
                Point the rear camera at the barcode. Hold steady until it beeps /
                closes.
              </p>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            {error ? (
              <p className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-950 dark:text-amber-100">
                {error}
              </p>
            ) : null}
            <div className="space-y-2">
              <Label htmlFor="barcode-manual">Barcode / SKU</Label>
              <Input
                id="barcode-manual"
                data-barcode-capture="true"
                className="min-h-11 font-mono"
                autoFocus
                autoComplete="off"
                inputMode="text"
                value={manual}
                onChange={(e) => setManual(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    submitCode(manual);
                  }
                }}
                placeholder="Scan with gun or type, then Enter"
              />
            </div>
            <Button
              type="button"
              className="min-h-11 w-full"
              onClick={() => submitCode(manual)}
            >
              Use barcode
            </Button>
            <p className="text-xs text-muted-foreground">
              Bluetooth / USB barcode guns work here — tap the field, then scan.
            </p>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
