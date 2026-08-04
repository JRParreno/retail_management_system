"use client";

import { useEffect, useRef, useState } from "react";
import JsBarcode from "jsbarcode";
import { Printer } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export type BarcodeLabelData = {
  barcode: string;
  name?: string;
  priceLabel?: string;
};

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  label: BarcodeLabelData | null;
};

function buildLabelHtml(data: BarcodeLabelData, svgMarkup: string, copies: number) {
  const safeName = (data.name ?? "").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const safePrice = (data.priceLabel ?? "").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const safeCode = data.barcode.replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const cards = Array.from({ length: copies }, () => {
    return `<div class="label">
      ${svgMarkup}
      ${safeName ? `<div class="name">${safeName}</div>` : ""}
      <div class="code">${safeCode}</div>
      ${safePrice ? `<div class="price">${safePrice}</div>` : ""}
    </div>`;
  }).join("");

  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Barcode ${safeCode}</title>
  <style>
    * { box-sizing: border-box; }
    body {
      margin: 0;
      padding: 8mm;
      font-family: Arial, Helvetica, sans-serif;
      color: #000;
    }
    .sheet {
      display: flex;
      flex-wrap: wrap;
      gap: 6mm;
      justify-content: flex-start;
    }
    .label {
      width: 54mm;
      min-height: 32mm;
      border: 1px dashed #bbb;
      padding: 3mm;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      text-align: center;
      break-inside: avoid;
      page-break-inside: avoid;
    }
    .label svg { max-width: 100%; height: auto; }
    .name {
      margin-top: 2mm;
      font-size: 9pt;
      font-weight: 700;
      line-height: 1.2;
      max-width: 100%;
      overflow: hidden;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
    }
    .code {
      margin-top: 1mm;
      font-size: 8pt;
      font-family: ui-monospace, Consolas, monospace;
      letter-spacing: 0.02em;
    }
    .price {
      margin-top: 1mm;
      font-size: 10pt;
      font-weight: 700;
    }
    @media print {
      body { padding: 4mm; }
      .label { border-color: #ddd; }
    }
  </style>
</head>
<body>
  <div class="sheet">${cards}</div>
  <script>
    window.onload = function () {
      window.focus();
      window.print();
    };
  </script>
</body>
</html>`;
}

export function BarcodeLabelPrintDialog({ open, onOpenChange, label }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [copies, setCopies] = useState("1");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!open || !label?.barcode.trim() || !svgRef.current) {
      setReady(false);
      return;
    }
    try {
      JsBarcode(svgRef.current, label.barcode.trim(), {
        format: "CODE128",
        displayValue: false,
        margin: 0,
        width: 2,
        height: 48,
        background: "#ffffff",
        lineColor: "#000000",
      });
      setReady(true);
    } catch {
      setReady(false);
      toast.error("Could not render this barcode for printing");
    }
  }, [open, label]);

  function handlePrint() {
    if (!label?.barcode.trim() || !svgRef.current || !ready) {
      toast.error("Generate or enter a barcode first");
      return;
    }
    const count = Number(copies);
    if (!Number.isInteger(count) || count < 1 || count > 40) {
      toast.error("Copies must be between 1 and 40");
      return;
    }

    const svgMarkup = svgRef.current.outerHTML;
    const html = buildLabelHtml(label, svgMarkup, count);
    const win = window.open("", "_blank", "noopener,noreferrer,width=720,height=640");
    if (!win) {
      toast.error("Pop-up blocked — allow pop-ups to print labels");
      return;
    }
    win.document.open();
    win.document.write(html);
    win.document.close();
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Print barcode label</DialogTitle>
        </DialogHeader>
        {label ? (
          <div className="space-y-4">
            <div className="flex flex-col items-center gap-2 rounded-xl border bg-white p-4 text-center text-black">
              <svg ref={svgRef} />
              {label.name ? (
                <p className="text-sm font-semibold leading-snug">{label.name}</p>
              ) : null}
              <p className="font-mono text-xs">{label.barcode}</p>
              {label.priceLabel ? (
                <p className="text-sm font-semibold">{label.priceLabel}</p>
              ) : null}
            </div>

            <div className="space-y-2">
              <Label htmlFor="label-copies">Copies</Label>
              <Input
                id="label-copies"
                className="min-h-11"
                inputMode="numeric"
                value={copies}
                onChange={(e) => setCopies(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                Prints sticker-sized labels (CODE128). Stick on the part or bin
                after printing.
              </p>
            </div>

            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <Button
                type="button"
                variant="outline"
                className="min-h-11"
                onClick={() => onOpenChange(false)}
              >
                Close
              </Button>
              <Button
                type="button"
                className="min-h-11 gap-2"
                disabled={!ready}
                onClick={handlePrint}
              >
                <Printer className="size-4" />
                Print labels
              </Button>
            </div>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
