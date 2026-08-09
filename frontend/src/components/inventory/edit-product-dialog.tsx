"use client";

import { useEffect, useMemo, useState } from "react";
import { Printer } from "lucide-react";
import { toast } from "sonner";

import {
  BarcodeLabelPrintDialog,
  type BarcodeLabelData,
} from "@/components/inventory/barcode-label-print";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { clientApi, toastError } from "@/lib/client-api";
import type { Product, ProductCategory } from "@/lib/types";
import { formatPeso } from "@/lib/types";

type Props = {
  product: Product | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  categories: ProductCategory[];
  onSaved: () => void;
};

export function EditProductDialog({
  product,
  open,
  onOpenChange,
  categories,
  onSaved,
}: Props) {
  const [name, setName] = useState("");
  const [brand, setBrand] = useState("");
  const [costPrice, setCostPrice] = useState("");
  const [sellingPrice, setSellingPrice] = useState("");
  const [stockQty, setStockQty] = useState("");
  const [minStock, setMinStock] = useState("");
  const [saving, setSaving] = useState(false);
  const [printLabel, setPrintLabel] = useState<BarcodeLabelData | null>(null);

  const categoryLabel = useMemo(() => {
    if (!product?.category_id) return "No category";
    return (
      categories.find((c) => c.id === product.category_id)?.name ?? "Category"
    );
  }, [categories, product]);

  useEffect(() => {
    if (!open || !product) return;
    setName(product.name);
    setBrand(product.brand ?? "");
    setCostPrice(product.cost_price);
    setSellingPrice(product.current_selling_price);
    setStockQty(String(product.stock_qty));
    setMinStock(String(product.min_stock_threshold));
  }, [open, product]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!product) return;

    const trimmedName = name.trim();
    if (!trimmedName) {
      toast.error("Enter the product name / title");
      return;
    }
    const cost = Number(costPrice);
    const sell = Number(sellingPrice);
    const nextStock = Number(stockQty);
    const nextMin = Number(minStock);
    if (!Number.isFinite(cost) || cost < 0) {
      toast.error("Enter a valid cost price");
      return;
    }
    if (!Number.isFinite(sell) || sell < 0) {
      toast.error("Enter a valid selling price");
      return;
    }
    if (!Number.isInteger(nextStock) || nextStock < 0) {
      toast.error("Stock must be a whole number ≥ 0");
      return;
    }
    if (!Number.isInteger(nextMin) || nextMin < 0) {
      toast.error("Min stock must be a whole number ≥ 0");
      return;
    }

    setSaving(true);
    try {
      // Name/brand/prices/min only — never barcode or category (set at create).
      // Price updates do not rewrite paid ticket snapshots / reports.
      await clientApi<Product>(`/products/${product.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: trimmedName,
          brand: brand.trim() || null,
          cost_price: cost.toFixed(2),
          current_selling_price: sell.toFixed(2),
          min_stock_threshold: nextMin,
        }),
      });

      const delta = nextStock - product.stock_qty;
      if (delta !== 0) {
        await clientApi(`/products/${product.id}/adjust`, {
          method: "POST",
          body: JSON.stringify({
            quantity_delta: delta,
            reason: "Inventory count / edit product stock",
          }),
        });
      }

      toast.success(
        delta !== 0
          ? `Updated “${trimmedName}” and set stock to ${nextStock}`
          : `Updated “${trimmedName}”`,
      );
      onOpenChange(false);
      onSaved();
    } catch (err) {
      toastError(err);
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Edit product</DialogTitle>
        </DialogHeader>
        {product ? (
          <form className="space-y-4" onSubmit={submit}>
            <p className="rounded-lg border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
              You can update the <strong>name</strong>, brand, prices, and stock.
              Barcode and category stay locked to avoid mistakes. Price changes
              apply to <strong>new sales only</strong> — paid tickets keep locked
              prices, so <strong>reports are not rewritten</strong>. Current sell:{" "}
              {formatPeso(product.current_selling_price)}.
            </p>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>Barcode (locked)</Label>
                <Input
                  className="min-h-11 font-mono"
                  value={product.barcode}
                  disabled
                />
              </div>
              <div className="space-y-2">
                <Label>Category (locked)</Label>
                <Input
                  className="min-h-11"
                  value={categoryLabel}
                  disabled
                />
              </div>
            </div>

            <Button
              type="button"
              variant="outline"
              className="min-h-11 w-full gap-2"
              onClick={() =>
                setPrintLabel({
                  barcode: product.barcode,
                  name: name.trim() || product.name,
                })
              }
            >
              <Printer className="size-4" />
              Print barcode label
            </Button>

            <div className="space-y-2">
              <Label htmlFor="edit-name">Name / title</Label>
              <Input
                id="edit-name"
                className="min-h-11"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="edit-brand">Brand (optional)</Label>
              <Input
                id="edit-brand"
                className="min-h-11"
                value={brand}
                onChange={(e) => setBrand(e.target.value)}
              />
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="edit-cost">Cost price</Label>
                <Input
                  id="edit-cost"
                  className="min-h-11"
                  inputMode="decimal"
                  value={costPrice}
                  onChange={(e) => setCostPrice(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-sell">Selling price</Label>
                <Input
                  id="edit-sell"
                  className="min-h-11"
                  inputMode="decimal"
                  value={sellingPrice}
                  onChange={(e) => setSellingPrice(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-stock">Stock (this branch)</Label>
                <Input
                  id="edit-stock"
                  className="min-h-11"
                  inputMode="numeric"
                  value={stockQty}
                  onChange={(e) => setStockQty(e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  Set the actual on-hand count. Difference is logged as an
                  adjustment.
                </p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-min">Min stock alert</Label>
                <Input
                  id="edit-min"
                  className="min-h-11"
                  inputMode="numeric"
                  value={minStock}
                  onChange={(e) => setMinStock(e.target.value)}
                />
              </div>
            </div>

            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <Button
                type="button"
                variant="outline"
                className="min-h-11"
                onClick={() => onOpenChange(false)}
              >
                Cancel
              </Button>
              <Button type="submit" className="min-h-11" disabled={saving}>
                {saving ? "Saving…" : "Save changes"}
              </Button>
            </div>
          </form>
        ) : null}
      </DialogContent>
    </Dialog>

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
