"use client";

import { useEffect, useState } from "react";
import { Scanner } from "@yudiel/react-qr-scanner";
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

export function BarcodeScanModal({ open, onOpenChange, onScan }: Props) {
  const [manual, setManual] = useState("");
  const [mode, setMode] = useState<"camera" | "manual">("camera");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      setManual("");
      setError(null);
      setMode("camera");
    }
  }, [open]);

  function submitCode(code: string) {
    const trimmed = code.trim();
    if (!trimmed) return;
    onScan(trimmed);
    onOpenChange(false);
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
            onClick={() => setMode("camera")}
          >
            <Camera className="size-4" /> Camera
          </Button>
          <Button
            type="button"
            variant={mode === "manual" ? "default" : "outline"}
            className="min-h-11 gap-2"
            onClick={() => setMode("manual")}
          >
            <Keyboard className="size-4" /> Manual
          </Button>
        </div>

        {mode === "camera" ? (
          <div className="space-y-2">
            <div className="overflow-hidden rounded-xl border bg-black">
              <Scanner
                constraints={{ facingMode: "environment" }}
                onScan={(results) => {
                  const text = results[0]?.rawValue;
                  if (text) submitCode(text);
                }}
                onError={() =>
                  setError("Camera unavailable — use Manual entry or a barcode gun.")
                }
                styles={{ container: { width: "100%" } }}
              />
            </div>
            {error ? (
              <p className="text-sm text-destructive">{error}</p>
            ) : (
              <p className="text-xs text-muted-foreground">
                Point the tablet camera at the barcode / QR
              </p>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            <div className="space-y-2">
              <Label htmlFor="barcode-manual">Barcode / SKU</Label>
              <Input
                id="barcode-manual"
                className="min-h-11"
                autoFocus
                value={manual}
                onChange={(e) => setManual(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") submitCode(manual);
                }}
                placeholder="Type or scan with gun then Enter"
              />
            </div>
            <Button
              type="button"
              className="min-h-11 w-full"
              onClick={() => submitCode(manual)}
            >
              Use barcode
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
