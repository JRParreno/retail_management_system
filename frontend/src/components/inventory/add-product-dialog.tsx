"use client";

import { useEffect, useRef, useState } from "react";
import { Printer, ScanBarcode, Sparkles } from "lucide-react";
import { toast } from "sonner";

import {
  BarcodeLabelPrintDialog,
  type BarcodeLabelData,
} from "@/components/inventory/barcode-label-print";
import { BarcodeScanModal } from "@/components/pos/barcode-scan-modal";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SearchableCombobox } from "@/components/ui/searchable-combobox";
import { clientApi, toastError } from "@/lib/client-api";
import type { Paginated, Product, ProductCategory } from "@/lib/types";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  categories: ProductCategory[];
  onCreated: () => void;
  onCategoriesChanged: (categories: ProductCategory[]) => void;
};

const emptyForm = {
  barcode: "",
  name: "",
  brand: "",
  categoryId: "",
  costPrice: "",
  sellingPrice: "",
  stockQty: "0",
  minStock: "0",
};

export function AddProductDialog({
  open,
  onOpenChange,
  categories,
  onCreated,
  onCategoriesChanged,
}: Props) {
  const [form, setForm] = useState(emptyForm);
  const [newCategory, setNewCategory] = useState("");
  const [saving, setSaving] = useState(false);
  const [scanOpen, setScanOpen] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [printLabel, setPrintLabel] = useState<BarcodeLabelData | null>(null);
  const barcodeRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) {
      setForm(emptyForm);
      setNewCategory("");
      setScanOpen(false);
      return;
    }
    const t = window.setTimeout(() => barcodeRef.current?.focus(), 50);
    return () => window.clearTimeout(t);
  }, [open]);

  function setField<K extends keyof typeof emptyForm>(
    key: K,
    value: (typeof emptyForm)[K],
  ) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function applyBarcode(code: string) {
    const trimmed = code.trim();
    if (!trimmed) return;
    setField("barcode", trimmed);

    try {
      const res = await clientApi<Paginated<Product>>(
        `/products?q=${encodeURIComponent(trimmed)}&page_size=20`,
      );
      const existing = res.items.find(
        (p) => p.barcode.toLowerCase() === trimmed.toLowerCase(),
      );
      if (existing) {
        toast.error(
          `Barcode “${trimmed}” already used by “${existing.name}”. Use a different barcode or edit that product.`,
        );
      } else {
        toast.success(`Barcode captured: ${trimmed}`);
      }
    } catch {
      toast.success(`Barcode captured: ${trimmed}`);
    }
  }

  async function generateBarcode() {
    setGenerating(true);
    try {
      // Prefer API when available; fall back to local unique RMS code.
      try {
        const res = await clientApi<{ barcode: string }>(
          "/products/barcode/generate",
          { method: "POST" },
        );
        setField("barcode", res.barcode);
        toast.success(`Generated barcode: ${res.barcode}`);
        return;
      } catch {
        /* fall through to local generation */
      }

      for (let attempt = 0; attempt < 12; attempt++) {
        const stamp = Date.now().toString().slice(-8);
        const rand = Math.floor(Math.random() * 10000)
          .toString()
          .padStart(4, "0");
        const candidate = `RMS${stamp}${rand}`;
        const res = await clientApi<Paginated<Product>>(
          `/products?q=${encodeURIComponent(candidate)}&page_size=20`,
        );
        const clash = res.items.some(
          (p) => p.barcode.toLowerCase() === candidate.toLowerCase(),
        );
        if (!clash) {
          setField("barcode", candidate);
          toast.success(`Generated barcode: ${candidate}`);
          return;
        }
      }
      toast.error("Could not generate a unique barcode — try again");
    } catch (err) {
      toastError(err);
    } finally {
      setGenerating(false);
    }
  }

  async function createCategory() {
    const name = newCategory.trim();
    if (!name) {
      toast.error("Enter a category name");
      return;
    }
    try {
      const created = await clientApi<ProductCategory>("/categories", {
        method: "POST",
        body: JSON.stringify({ name }),
      });
      onCategoriesChanged(
        [...categories, created].sort((a, b) => a.name.localeCompare(b.name)),
      );
      setField("categoryId", created.id);
      setNewCategory("");
      toast.success(`Category “${created.name}” added`);
    } catch (err) {
      toastError(err);
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const barcode = form.barcode.trim();
    const name = form.name.trim();
    if (!barcode) {
      toast.error("Scan or enter the product barcode");
      barcodeRef.current?.focus();
      return;
    }
    if (!name) {
      toast.error("Enter the product name / title");
      return;
    }
    const cost = Number(form.costPrice);
    const sell = Number(form.sellingPrice);
    const stock = Number(form.stockQty);
    const minStock = Number(form.minStock);
    if (!Number.isFinite(cost) || cost < 0) {
      toast.error("Enter a valid cost price");
      return;
    }
    if (!Number.isFinite(sell) || sell < 0) {
      toast.error("Enter a valid selling price");
      return;
    }
    if (!Number.isInteger(stock) || stock < 0) {
      toast.error("Opening stock must be a whole number ≥ 0");
      return;
    }
    if (!Number.isInteger(minStock) || minStock < 0) {
      toast.error("Min stock must be a whole number ≥ 0");
      return;
    }

    setSaving(true);
    try {
      await clientApi<Product>("/products", {
        method: "POST",
        body: JSON.stringify({
          barcode,
          name,
          brand: form.brand.trim() || null,
          cost_price: cost.toFixed(2),
          current_selling_price: sell.toFixed(2),
          stock_qty: stock,
          min_stock_threshold: minStock,
          category_id: form.categoryId || null,
          is_active: true,
        }),
      });
      toast.success(`Added “${name}”`);
      onOpenChange(false);
      onCreated();
      setPrintLabel({
        barcode,
        name,
      });
    } catch (err) {
      toastError(err);
    } finally {
      setSaving(false);
    }
  }

  function openPrintPreview() {
    const barcode = form.barcode.trim();
    if (!barcode) {
      toast.error("Generate or enter a barcode first");
      return;
    }
    const sell = Number(form.sellingPrice);
    setPrintLabel({
      barcode,
      name: form.name.trim() || undefined,
    });
  }

  return (
    <>
      <Dialog
        open={open}
        disablePointerDismissal
        onOpenChange={(nextOpen, eventDetails) => {
          if (
            !nextOpen &&
            (saving ||
              eventDetails.reason === "outside-press" ||
              eventDetails.reason === "escape-key")
          ) {
            eventDetails.cancel();
            return;
          }
          onOpenChange(nextOpen);
        }}
      >
        <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Add product</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Prefer the real barcode on the part when it has one. For loose parts
            without a code, use <strong>Generate</strong>, then fill in name,
            category, and prices. Price is locked into each sale when the part is
            added, so later price changes will not rewrite reports.
          </p>

          <form className="space-y-4" onSubmit={submit}>
            <div className="space-y-2">
              <Label htmlFor="product-barcode">Barcode</Label>
              <div className="flex flex-col gap-2 sm:flex-row">
                <Input
                  id="product-barcode"
                  ref={barcodeRef}
                  className="min-h-11 font-mono sm:flex-1"
                  placeholder="Scan, generate, or type"
                  value={form.barcode}
                  onChange={(e) => setField("barcode", e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      void applyBarcode(form.barcode);
                    }
                  }}
                />
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant="secondary"
                    className="min-h-11 flex-1 gap-2 sm:flex-none"
                    disabled={generating}
                    onClick={() => void generateBarcode()}
                  >
                    <Sparkles className="size-4" />
                    {generating ? "…" : "Generate"}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    className="min-h-11 flex-1 gap-2 sm:flex-none"
                    onClick={() => setScanOpen(true)}
                  >
                    <ScanBarcode className="size-4" />
                    Scan
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    className="min-h-11 flex-1 gap-2 sm:flex-none"
                    disabled={!form.barcode.trim()}
                    onClick={openPrintPreview}
                  >
                    <Printer className="size-4" />
                    Print
                  </Button>
                </div>
              </div>
              <p className="text-xs text-muted-foreground">
                Scan, generate an internal <span className="font-mono">RMS…</span>{" "}
                code, then print a sticker label for the part or bin.
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="product-name">Name / title</Label>
              <Input
                id="product-name"
                className="min-h-11"
                placeholder="e.g. Oil filter — Honda Wave"
                value={form.name}
                onChange={(e) => setField("name", e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="product-brand">Brand (optional)</Label>
              <Input
                id="product-brand"
                className="min-h-11"
                placeholder="e.g. Motul, NGK"
                value={form.brand}
                onChange={(e) => setField("brand", e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label>Category</Label>
              <SearchableCombobox
                value={form.categoryId || "none"}
                onValueChange={(v) =>
                  setField("categoryId", v === "none" ? "" : v)
                }
                placeholder="Select category (optional)"
                searchPlaceholder="Search category…"
                emptyText="No categories yet — add one below."
                options={[
                  { value: "none", label: "No category" },
                  ...categories.map((c) => ({
                    value: c.id,
                    label: c.name,
                  })),
                ]}
              />
              <div className="flex gap-2">
                <Input
                  className="min-h-11"
                  placeholder="New category name"
                  value={newCategory}
                  onChange={(e) => setNewCategory(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      void createCategory();
                    }
                  }}
                />
                <Button
                  type="button"
                  variant="secondary"
                  className="min-h-11 shrink-0"
                  onClick={() => void createCategory()}
                >
                  Add category
                </Button>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="product-cost">Cost price</Label>
                <Input
                  id="product-cost"
                  className="min-h-11"
                  inputMode="decimal"
                  placeholder="0.00"
                  value={form.costPrice}
                  onChange={(e) => setField("costPrice", e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="product-sell">Selling price</Label>
                <Input
                  id="product-sell"
                  className="min-h-11"
                  inputMode="decimal"
                  placeholder="0.00"
                  value={form.sellingPrice}
                  onChange={(e) => setField("sellingPrice", e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="product-stock">Opening stock (this branch)</Label>
                <Input
                  id="product-stock"
                  className="min-h-11"
                  inputMode="numeric"
                  value={form.stockQty}
                  onChange={(e) => setField("stockQty", e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="product-min">Min stock alert</Label>
                <Input
                  id="product-min"
                  className="min-h-11"
                  inputMode="numeric"
                  value={form.minStock}
                  onChange={(e) => setField("minStock", e.target.value)}
                />
              </div>
            </div>

            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <Button
                type="button"
                variant="outline"
                className="min-h-11"
                disabled={saving}
                onClick={() => onOpenChange(false)}
              >
                Cancel
              </Button>
              <Button type="submit" className="min-h-11" disabled={saving}>
                {saving ? "Saving…" : "Save product"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      <BarcodeScanModal
        open={scanOpen}
        onOpenChange={setScanOpen}
        onScan={(code) => {
          void applyBarcode(code);
        }}
      />

      <BarcodeLabelPrintDialog
        open={printLabel != null}
        onOpenChange={(next) => {
          if (!next) setPrintLabel(null);
        }}
        label={printLabel}
      />
    </>
  );
}
