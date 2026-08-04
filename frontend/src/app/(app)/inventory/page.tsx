"use client";

import { useEffect, useMemo, useState } from "react";
import { FileDown, Plus, Printer } from "lucide-react";
import { toast } from "sonner";

import { AddProductDialog } from "@/components/inventory/add-product-dialog";
import {
  BarcodeLabelPrintDialog,
  type BarcodeLabelData,
} from "@/components/inventory/barcode-label-print";
import { EditProductDialog } from "@/components/inventory/edit-product-dialog";
import { useBranch } from "@/components/branch/branch-context";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SearchableCombobox } from "@/components/ui/searchable-combobox";
import { clientApi, toastError } from "@/lib/client-api";
import type { Paginated, Product, ProductCategory } from "@/lib/types";
import { formatPeso } from "@/lib/types";

function formatSnapshotDate(date: Date) {
  return date.toLocaleString("en-PH", {
    weekday: "short",
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: true,
  });
}

function formatSnapshotFileStamp(date: Date) {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}-${pad(date.getHours())}${pad(date.getMinutes())}`;
}

export default function InventoryPage() {
  const { activeBranch, user } = useBranch();
  const isAdmin = user?.role === "ADMIN";
  const [items, setItems] = useState<Product[]>([]);
  const [total, setTotal] = useState(0);
  const [categories, setCategories] = useState<ProductCategory[]>([]);
  const [brands, setBrands] = useState<string[]>([]);
  const [q, setQ] = useState("");
  const [categoryId, setCategoryId] = useState<string>("all");
  const [brand, setBrand] = useState<string>("all");
  const [adjustId, setAdjustId] = useState<string | null>(null);
  const [delta, setDelta] = useState("0");
  const [snapshotAt, setSnapshotAt] = useState(() => new Date());
  const [addOpen, setAddOpen] = useState(false);
  const [editProduct, setEditProduct] = useState<Product | null>(null);
  const [printLabel, setPrintLabel] = useState<BarcodeLabelData | null>(null);

  const categoryName = useMemo(() => {
    if (categoryId === "all") return "All categories";
    return categories.find((c) => c.id === categoryId)?.name ?? "Category";
  }, [categories, categoryId]);

  const brandLabel = brand === "all" ? "All brands" : brand;

  const filterSummary = useMemo(() => {
    const parts = [brandLabel, categoryName];
    if (q.trim()) parts.push(`Search: “${q.trim()}”`);
    return parts.join(" · ");
  }, [brandLabel, categoryName, q]);

  const totalUnits = useMemo(
    () => items.reduce((sum, p) => sum + p.stock_qty, 0),
    [items],
  );

  const lowStockCount = useMemo(
    () => items.filter((p) => p.stock_qty <= p.min_stock_threshold).length,
    [items],
  );

  async function load() {
    try {
      const params = new URLSearchParams({ page_size: "100" });
      if (q.trim()) params.set("q", q.trim());
      if (categoryId !== "all") params.set("category_id", categoryId);
      if (brand !== "all") params.set("brand", brand);
      const [products, cats, brandList] = await Promise.all([
        clientApi<Paginated<Product>>(`/products?${params}`),
        clientApi<ProductCategory[]>("/categories"),
        clientApi<string[]>("/products/brands"),
      ]);
      setItems(products.items);
      setTotal(products.total);
      setCategories(cats);
      setBrands(brandList);
      setSnapshotAt(new Date());
    } catch (err) {
      toastError(err);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [categoryId, brand]);

  async function adjust(productId: string) {
    const qtyDelta = Number(delta);
    if (!Number.isInteger(qtyDelta) || qtyDelta === 0) {
      toast.error("Enter a non-zero whole number (e.g. +5 or -2)");
      return;
    }
    const product = items.find((p) => p.id === productId);
    try {
      await clientApi(`/products/${productId}/adjust`, {
        method: "POST",
        body: JSON.stringify({
          quantity_delta: qtyDelta,
          reason: "Manual adjustment",
        }),
      });
      const after = (product?.stock_qty ?? 0) + qtyDelta;
      toast.success(
        `Stock updated${product ? `: ${product.stock_qty} → ${after}` : ""}`,
      );
      setAdjustId(null);
      setDelta("0");
      await load();
    } catch (err) {
      toastError(err);
    }
  }

  function exportPdf() {
    const stamped = new Date();
    setSnapshotAt(stamped);
    const previous = document.title;
    document.title = `MotoShop-Inventory-${formatSnapshotFileStamp(stamped)}`;
    // Wait for snapshot timestamp to paint before opening the print dialog
    window.setTimeout(() => {
      window.print();
      document.title = previous;
    }, 50);
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Inventory</h1>
          <p className="text-sm text-muted-foreground">
            Search and filter by brand, category, name, or barcode — export PDF
            for stock audits
            {isAdmin ? ". Admins can add products by scanning the real barcode." : ""}
          </p>
        </div>
        <div className="no-print flex flex-wrap gap-2">
          {isAdmin ? (
            <Button
              className="min-h-11 gap-2"
              onClick={() => setAddOpen(true)}
            >
              <Plus className="size-4" />
              Add product
            </Button>
          ) : null}
          <Button
            className="min-h-11 gap-2"
            variant="outline"
            disabled={!items.length}
            onClick={exportPdf}
          >
            <FileDown className="size-4" />
            Export PDF
          </Button>
        </div>
      </div>

      <div className="no-print flex flex-col gap-2 lg:flex-row">
        <Input
          className="min-h-11"
          placeholder="Search name, barcode, or brand"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && load()}
        />
        <SearchableCombobox
          className="lg:w-48"
          value={brand}
          onValueChange={setBrand}
          placeholder="All brands"
          searchPlaceholder="Search brand…"
          emptyText="No brands found."
          options={[
            { value: "all", label: "All brands" },
            ...brands.map((b) => ({ value: b, label: b })),
          ]}
        />
        <SearchableCombobox
          className="lg:w-48"
          value={categoryId}
          onValueChange={setCategoryId}
          placeholder="All categories"
          searchPlaceholder="Search category…"
          emptyText="No categories found."
          options={[
            { value: "all", label: "All categories" },
            ...categories.map((c) => ({ value: c.id, label: c.name })),
          ]}
        />
        <Button className="min-h-11" onClick={load}>
          Search
        </Button>
      </div>

      <div className="report-screen-only overflow-x-auto rounded-xl border bg-card">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead className="border-b bg-muted/40">
            <tr>
              <th className="px-3 py-3">Product</th>
              <th className="px-3 py-3">Brand</th>
              <th className="px-3 py-3">Barcode</th>
              <th className="px-3 py-3">Price</th>
              <th className="px-3 py-3">Stock</th>
              <th className="px-3 py-3" />
            </tr>
          </thead>
          <tbody>
            {items.map((p) => (
              <tr key={p.id} className="border-b last:border-0">
                <td className="px-3 py-3 font-medium">{p.name}</td>
                <td className="px-3 py-3 text-muted-foreground">
                  {p.brand ?? "—"}
                </td>
                <td className="px-3 py-3 text-muted-foreground">{p.barcode}</td>
                <td className="px-3 py-3 tabular-nums">
                  {formatPeso(p.current_selling_price)}
                </td>
                <td className="px-3 py-3">
                  <div className="flex items-center gap-2">
                    <span className="tabular-nums">{p.stock_qty}</span>
                    {p.stock_qty <= p.min_stock_threshold ? (
                      <Badge variant="destructive">Low</Badge>
                    ) : null}
                  </div>
                </td>
                <td className="px-3 py-3 text-right">
                  {adjustId === p.id ? (
                    <div className="flex flex-wrap items-center justify-end gap-2">
                      <span className="text-xs text-muted-foreground">
                        ± qty
                      </span>
                      <Input
                        className="h-9 w-20"
                        inputMode="numeric"
                        placeholder="+5"
                        value={delta}
                        onChange={(e) => setDelta(e.target.value)}
                      />
                      <Button size="sm" onClick={() => adjust(p.id)}>
                        Apply
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => {
                          setAdjustId(null);
                          setDelta("0");
                        }}
                      >
                        Cancel
                      </Button>
                    </div>
                  ) : (
                    <div className="flex justify-end gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() =>
                          setPrintLabel({
                            barcode: p.barcode,
                            name: p.name,
                            priceLabel: formatPeso(p.current_selling_price),
                          })
                        }
                      >
                        <Printer className="size-3.5" />
                        Label
                      </Button>
                      {isAdmin ? (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => setEditProduct(p)}
                        >
                          Edit
                        </Button>
                      ) : null}
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setAdjustId(p.id);
                          setDelta("0");
                        }}
                      >
                        Adjust
                      </Button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
            {!items.length ? (
              <tr>
                <td colSpan={6} className="px-3 py-6 text-muted-foreground">
                  No products match these filters.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      {/* Print / PDF audit sheet */}
      <div className="report-print-area report-print-only">
        <h1>MotoShop RMS — Inventory Stock Snapshot</h1>
        <p className="report-print-meta">
          <strong>Snapshot date:</strong> {formatSnapshotDate(snapshotAt)}
          <br />
          <strong>Branch:</strong>{" "}
          {activeBranch
            ? `${activeBranch.name} (${activeBranch.code})`
            : "—"}
          <br />
          <strong>Filters:</strong> {filterSummary}
          <br />
          <strong>SKUs listed:</strong> {items.length}
          {total > items.length ? ` of ${total}` : ""}
          {" · "}
          <strong>System units:</strong> {totalUnits}
          {" · "}
          <strong>Low stock:</strong> {lowStockCount}
          <br />
          Use this sheet to count physical stock and compare against system qty.
        </p>

        <table className="report-print-table inventory-print-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Product</th>
              <th>Brand</th>
              <th>Barcode</th>
              <th>System qty</th>
              <th>Physical count</th>
              <th>Variance</th>
              <th>Notes</th>
            </tr>
          </thead>
          <tbody>
            {items.map((p, index) => (
              <tr key={p.id}>
                <td>{index + 1}</td>
                <td>
                  {p.name}
                  {p.stock_qty <= p.min_stock_threshold ? " ★" : ""}
                </td>
                <td>{p.brand ?? "—"}</td>
                <td>{p.barcode}</td>
                <td className="inventory-qty">{p.stock_qty}</td>
                <td className="inventory-blank" />
                <td className="inventory-blank" />
                <td className="inventory-blank" />
              </tr>
            ))}
          </tbody>
        </table>

        <p className="report-print-meta" style={{ marginTop: "16pt" }}>
          ★ = at or below minimum stock threshold
          <br />
          Variance = Physical count − System qty (write after counting)
        </p>

        <div className="inventory-signoff">
          <div>
            <p>Counted by: _______________________________</p>
            <p>Date / time: _______________________________</p>
          </div>
          <div>
            <p>Verified by: _______________________________</p>
            <p>Date / time: _______________________________</p>
          </div>
        </div>
      </div>

      {isAdmin ? (
        <>
          <AddProductDialog
            open={addOpen}
            onOpenChange={setAddOpen}
            categories={categories}
            onCategoriesChanged={setCategories}
            onCreated={() => {
              void load();
            }}
          />
          <EditProductDialog
            product={editProduct}
            open={editProduct != null}
            onOpenChange={(open) => {
              if (!open) setEditProduct(null);
            }}
            categories={categories}
            onSaved={() => {
              void load();
            }}
          />
        </>
      ) : null}

      <BarcodeLabelPrintDialog
        open={printLabel != null}
        onOpenChange={(open) => {
          if (!open) setPrintLabel(null);
        }}
        label={printLabel}
      />
    </div>
  );
}
