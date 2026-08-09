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
};

function esc(value: string) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function barcodeSvgMarkup(code: string): string | null {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  try {
    JsBarcode(svg, code.trim(), {
      format: "CODE128",
      displayValue: false,
      margin: 0,
      width: 2,
      height: 48,
      background: "#ffffff",
      lineColor: "#000000",
    });
  } catch {
    return null;
  }
  return svg.outerHTML;
}

function buildSheetHtml(labels: { data: BarcodeLabelData; svg: string }[]) {
  const cards = labels
    .map(({ data, svg }) => {
      const safeName = esc(data.name ?? "");
      const safeCode = esc(data.barcode);
      return `<div class="label">
      ${svg}
      ${safeName ? `<div class="name">${safeName}</div>` : ""}
      <div class="code">${safeCode}</div>
    </div>`;
    })
    .join("");

  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Barcode labels</title>
  <style>
    * { box-sizing: border-box; }
    body {
      margin: 0;
      padding: 8mm;
      font-family: Arial, Helvetica, sans-serif;
      color: #000;
      background: #fff;
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
    @media print {
      body { padding: 4mm; }
      .label { border-color: #ddd; }
    }
  </style>
</head>
<body>
  <div class="sheet">${cards}</div>
</body>
</html>`;
}

/** Print one or many barcode labels (CODE128 sticker sheet). */
export function printBarcodeLabels(
  labels: BarcodeLabelData[],
  copiesPerLabel = 1,
) {
  const expanded: BarcodeLabelData[] = [];
  for (const label of labels) {
    const code = label.barcode.trim();
    if (!code) continue;
    for (let i = 0; i < copiesPerLabel; i += 1) {
      expanded.push({ ...label, barcode: code });
    }
  }
  if (!expanded.length) {
    toast.error("No barcodes to print");
    return;
  }

  const rendered: { data: BarcodeLabelData; svg: string }[] = [];
  const failed: string[] = [];
  for (const label of expanded) {
    const svg = barcodeSvgMarkup(label.barcode);
    if (!svg) {
      failed.push(label.barcode);
      continue;
    }
    rendered.push({ data: label, svg });
  }

  if (!rendered.length) {
    toast.error("Could not render barcodes for printing");
    return;
  }
  if (failed.length) {
    toast.error(`Skipped ${failed.length} invalid barcode(s)`);
  }

  const html = buildSheetHtml(rendered);
  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const popup = window.open(url, "_blank", "width=720,height=640");
  if (!popup) {
    URL.revokeObjectURL(url);
    toast.error("Pop-up blocked — allow pop-ups to print barcode labels");
    return;
  }

  let printed = false;
  const triggerPrint = () => {
    if (printed) return;
    printed = true;
    try {
      popup.focus();
      popup.print();
    } catch {
      // User can print manually.
    }
  };

  try {
    popup.addEventListener("load", () => {
      window.setTimeout(triggerPrint, 300);
    });
  } catch {
    // Fallback timeout below.
  }
  window.setTimeout(triggerPrint, 700);
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  label: BarcodeLabelData | null;
};

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
    if (!label?.barcode.trim() || !ready) {
      toast.error("Generate or enter a barcode first");
      return;
    }
    const count = Number(copies);
    if (!Number.isInteger(count) || count < 1 || count > 40) {
      toast.error("Copies must be between 1 and 40");
      return;
    }
    printBarcodeLabels([label], count);
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
