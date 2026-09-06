"use client";

import { useEffect, useRef, useState } from "react";
import { FileSpreadsheet, Upload } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { clientApi, toastError } from "@/lib/client-api";
import type { ProductImportResponse } from "@/lib/types";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onImported: () => void;
};

export function ImportProductsDialog({
  open,
  onOpenChange,
  onImported,
}: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [result, setResult] = useState<ProductImportResponse | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) {
      setFile(null);
      setResult(null);
      setUploading(false);
      setDownloading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }, [open]);

  async function downloadTemplate() {
    setDownloading(true);
    try {
      const res = await fetch("/api/proxy/products/import/template");
      if (!res.ok) {
        let detail = res.statusText;
        try {
          const data = await res.json();
          detail =
            typeof data.detail === "string" ? data.detail : res.statusText;
        } catch {
          /* ignore */
        }
        throw new Error(detail || "Failed to download template");
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "inventory-import-template.xlsx";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success("Template downloaded");
    } catch (err) {
      toastError(err);
    } finally {
      setDownloading(false);
    }
  }

  async function handleUpload() {
    if (!file) {
      toast.error("Choose an .xlsx file first");
      return;
    }
    setUploading(true);
    setResult(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await clientApi<ProductImportResponse>("/products/import", {
        method: "POST",
        body: form,
      });
      setResult(res);
      if (res.created > 0 || (res.updated ?? 0) > 0) {
        const parts = [];
        if (res.created > 0) {
          parts.push(
            `Created ${res.created} product${res.created === 1 ? "" : "s"}`,
          );
        }
        if ((res.updated ?? 0) > 0) {
          parts.push(
            `updated fitment on ${res.updated} existing`,
          );
        }
        toast.success(parts.join(" · "));
        onImported();
      } else if (res.errors === 0 && res.skipped > 0) {
        toast.message("No new products — all barcodes already exist");
      } else {
        toast.error("Import finished with errors — review the report");
      }
    } catch (err) {
      toastError(err);
    } finally {
      setUploading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Import products from Excel</DialogTitle>
          <DialogDescription>
            Physical barcode preferred. Leave barcode blank to auto-generate an
            internal RMS code — duplicates without a barcode are skipped when
            the same name + brand already exists. Opening stock applies to the
            active branch. Use{" "}
            <span className="font-mono">applicable_model_1</span>…{" "}
            <span className="font-mono">applicable_model_8</span> dropdowns
            (one model per column). Existing barcodes can update fitment when
            those columns are filled.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="rounded-lg border border-dashed p-4">
            <p className="text-sm font-medium">1. Download the template</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Keep the barcode column as text. Brand and each applicable model
              column have dropdowns — pick one model per column (e.g. Click in
              model 1, Wave in model 2). Leave unused model columns blank.
            </p>
            <Button
              type="button"
              variant="outline"
              className="mt-3 min-h-11 gap-2"
              disabled={downloading}
              onClick={() => void downloadTemplate()}
            >
              <FileSpreadsheet className="size-4" />
              {downloading ? "Downloading…" : "Download template"}
            </Button>
          </div>

          <div className="rounded-lg border border-dashed p-4">
            <p className="text-sm font-medium">2. Upload filled .xlsx</p>
            <input
              ref={inputRef}
              type="file"
              accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              className="mt-3 block w-full text-sm file:mr-3 file:rounded-md file:border-0 file:bg-muted file:px-3 file:py-2 file:text-sm file:font-medium"
              onChange={(e) => {
                const next = e.target.files?.[0] ?? null;
                setFile(next);
                setResult(null);
              }}
            />
            {file ? (
              <p className="mt-2 truncate text-xs text-muted-foreground">
                Selected: {file.name}
              </p>
            ) : null}
          </div>

          {result ? (
            <div className="space-y-2 rounded-lg border p-3">
              <p className="text-sm font-medium">
                Created {result.created} · Updated {result.updated ?? 0} ·
                Skipped {result.skipped} · Errors {result.errors}
              </p>
              <div className="max-h-48 overflow-y-auto text-xs">
                <table className="w-full">
                  <thead className="sticky top-0 bg-popover text-left text-muted-foreground">
                    <tr>
                      <th className="py-1 pr-2 font-medium">Row</th>
                      <th className="py-1 pr-2 font-medium">Status</th>
                      <th className="py-1 font-medium">Detail</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.rows.map((row) => (
                      <tr key={`${row.row}-${row.status}-${row.barcode ?? ""}`}>
                        <td className="py-1 pr-2 align-top tabular-nums">
                          {row.row}
                        </td>
                        <td className="py-1 pr-2 align-top capitalize">
                          {row.status}
                        </td>
                        <td className="py-1 align-top">
                          {[row.barcode, row.message].filter(Boolean).join(" — ")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}
        </div>

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            Close
          </Button>
          <Button
            type="button"
            className="gap-2"
            disabled={!file || uploading}
            onClick={() => void handleUpload()}
          >
            <Upload className="size-4" />
            {uploading ? "Importing…" : "Import"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
