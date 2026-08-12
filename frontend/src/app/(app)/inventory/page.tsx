"use client";

import { useEffect, useMemo, useState } from "react";
import { FileDown, Plus, Printer, RotateCcw, Trash2, Upload } from "lucide-react";
import { toast } from "sonner";

import { AddProductDialog } from "@/components/inventory/add-product-dialog";
import {
  BarcodeLabelPrintDialog,
  printBarcodeLabels,
  type BarcodeLabelData,
} from "@/components/inventory/barcode-label-print";
import { EditProductDialog } from "@/components/inventory/edit-product-dialog";
import { ImportProductsDialog } from "@/components/inventory/import-products-dialog";
import { useBranch } from "@/components/branch/branch-context";
import { useShop } from "@/components/shop/shop-context";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SearchableCombobox } from "@/components/ui/searchable-combobox";
import { clientApi, toastError } from "@/lib/client-api";
import type {
  Paginated,
  Product,
  ProductCategory,
  ProductDeletionImpact,
} from "@/lib/types";
import { formatPeso } from "@/lib/types";

type ProductLifecycle = "active" | "disabled" | "deleted" | "all";

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

function fileSafeName(name: string) {
  return (
    name
      .trim()
      .replace(/[^a-zA-Z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "") || "Shop"
  );
}

export default function InventoryPage() {
  const { activeBranch, user } = useBranch();
  const { settings } = useShop();
  const isAdmin = user?.role === "ADMIN";
  const [items, setItems] = useState<Product[]>([]);
  const [total, setTotal] = useState(0);
  const [categories, setCategories] = useState<ProductCategory[]>([]);
  const [brands, setBrands] = useState<string[]>([]);
  const [q, setQ] = useState("");
  const [categoryId, setCategoryId] = useState<string>("all");
  const [brand, setBrand] = useState<string>("all");
  const [lifecycle, setLifecycle] = useState<ProductLifecycle>("active");
  const [snapshotAt, setSnapshotAt] = useState(() => new Date());
  const [addOpen, setAddOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [editProduct, setEditProduct] = useState<Product | null>(null);
  const [printLabel, setPrintLabel] = useState<BarcodeLabelData | null>(null);
  const [lifecycleBusyId, setLifecycleBusyId] = useState<string | null>(null);

  const categoryName = useMemo(() => {
    if (categoryId === "all") return "All categories";
    return categories.find((c) => c.id === categoryId)?.name ?? "Category";
  }, [categories, categoryId]);

  const brandLabel = brand === "all" ? "All brands" : brand;

  const filterSummary = useMemo(() => {
    const parts = [brandLabel, categoryName, `Status: ${lifecycle}`];
    if (q.trim()) parts.push(`Search: “${q.trim()}”`);
    return parts.join(" · ");
  }, [brandLabel, categoryName, lifecycle, q]);

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
      params.set("lifecycle", lifecycle);
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
  }, [categoryId, brand, lifecycle]);

  async function setProductEnabled(product: Product, isActive: boolean) {
    setLifecycleBusyId(product.id);
    try {
      await clientApi(`/products/${product.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: isActive }),
      });
      toast.success(`${product.name} ${isActive ? "enabled" : "disabled"}`);
      await load();
    } catch (err) {
      toastError(err);
    } finally {
      setLifecycleBusyId(null);
    }
  }

  async function softDeleteProduct(product: Product) {
    if (
      !window.confirm(
        `Soft delete “${product.name}”? It will be hidden from sales but can be restored.`,
      )
    ) {
      return;
    }
    setLifecycleBusyId(product.id);
    try {
      await clientApi(`/products/${product.id}`, { method: "DELETE" });
      toast.success(`${product.name} moved to deleted products`);
      await load();
    } catch (err) {
      toastError(err);
    } finally {
      setLifecycleBusyId(null);
    }
  }

  async function restoreProduct(product: Product) {
    setLifecycleBusyId(product.id);
    try {
      await clientApi(`/products/${product.id}/restore`, { method: "POST" });
      toast.success(`${product.name} restored as disabled`);
      await load();
    } catch (err) {
      toastError(err);
    } finally {
      setLifecycleBusyId(null);
    }
  }

  async function hardDeleteProduct(product: Product) {
    setLifecycleBusyId(product.id);
    try {
      const impact = await clientApi<ProductDeletionImpact>(
        `/products/${product.id}/deletion-impact`,
      );
      if (!impact.can_hard_delete) {
        const history =
          impact.transaction_lines +
          impact.stock_adjustments +
          impact.transfer_lines +
          impact.return_lines;
        toast.error(
          history > 0
            ? `Permanent deletion blocked by ${history} inventory/history record(s)`
            : "Permanent deletion requires zero stock in every branch",
        );
        return;
      }
      const confirmation = window.prompt(
        `Permanent deletion cannot be undone. Type the product name to continue:\n${product.name}`,
      );
      if (confirmation !== product.name) return;
      await clientApi(`/products/${product.id}/hard`, { method: "DELETE" });
      toast.success(`${product.name} permanently deleted`);
      await load();
    } catch (err) {
      toastError(err);
    } finally {
      setLifecycleBusyId(null);
    }
  }

  function exportPdf() {
    const stamped = new Date();
    setSnapshotAt(stamped);
    const previous = document.title;
    document.title = `${fileSafeName(settings.business_name)}-Inventory-${formatSnapshotFileStamp(stamped)}`;
    // Wait for snapshot timestamp to paint before opening the print dialog
    window.setTimeout(() => {
      window.print();
      document.title = previous;
    }, 50);
  }

  function exportBarcodes() {
    if (!items.length) {
      toast.error("No products to export");
      return;
    }
    printBarcodeLabels(
      items.map((p) => ({
        barcode: p.barcode,
        name: p.name,
      })),
      1,
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Inventory</h1>
          <p className="text-sm text-muted-foreground">
            Search and filter by brand, category, name, or barcode — export PDF
            or barcode labels for the filtered list
            {isAdmin ? ". Admins can add products by scanning the real barcode or import Excel." : ""}
          </p>
        </div>
        <div className="no-print flex flex-wrap gap-2">
          {isAdmin ? (
            <>
              <Button
                className="min-h-11 gap-2"
                onClick={() => setAddOpen(true)}
              >
                <Plus className="size-4" />
                Add product
              </Button>
              <Button
                className="min-h-11 gap-2"
                variant="outline"
                onClick={() => setImportOpen(true)}
              >
                <Upload className="size-4" />
                Import Excel
              </Button>
            </>
          ) : null}
          <Button
            className="min-h-11 gap-2"
            variant="outline"
            disabled={!items.length}
            onClick={exportBarcodes}
          >
            <Printer className="size-4" />
            Export barcodes
          </Button>
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
        <SearchableCombobox
          className="lg:w-44"
          value={lifecycle}
          onValueChange={(value) => setLifecycle(value as ProductLifecycle)}
          placeholder="Product status"
          searchPlaceholder="Search status…"
          emptyText="No status found."
          options={[
            { value: "active", label: "Active" },
            { value: "disabled", label: "Disabled" },
            { value: "deleted", label: "Deleted" },
            { value: "all", label: "All statuses" },
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
              <th className="px-3 py-3">Status</th>
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
                <td className="px-3 py-3">
                  {p.deleted_at ? (
                    <Badge variant="destructive">Deleted</Badge>
                  ) : p.is_active ? (
                    <Badge>Active</Badge>
                  ) : (
                    <Badge variant="secondary">Disabled</Badge>
                  )}
                </td>
                <td className="px-3 py-3 text-right">
                  <div className="flex flex-wrap justify-end gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        setPrintLabel({
                          barcode: p.barcode,
                          name: p.name,
                        })
                      }
                    >
                      <Printer className="size-3.5" />
                      Label
                    </Button>
                    {isAdmin ? (
                      <>
                        {!p.deleted_at ? (
                          <>
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={lifecycleBusyId === p.id}
                              onClick={() =>
                                void setProductEnabled(p, !p.is_active)
                              }
                            >
                              {p.is_active ? "Disable" : "Enable"}
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => setEditProduct(p)}
                            >
                              Edit
                            </Button>
                            <Button
                              size="sm"
                              variant="destructive"
                              disabled={lifecycleBusyId === p.id}
                              onClick={() => void softDeleteProduct(p)}
                            >
                              <Trash2 className="size-3.5" />
                              Delete
                            </Button>
                          </>
                        ) : (
                          <>
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={lifecycleBusyId === p.id}
                              onClick={() => void restoreProduct(p)}
                            >
                              <RotateCcw className="size-3.5" />
                              Restore
                            </Button>
                            <Button
                              size="sm"
                              variant="destructive"
                              disabled={lifecycleBusyId === p.id}
                              onClick={() => void hardDeleteProduct(p)}
                            >
                              <Trash2 className="size-3.5" />
                              Permanent
                            </Button>
                          </>
                        )}
                      </>
                    ) : null}
                  </div>
                </td>
              </tr>
            ))}
            {!items.length ? (
              <tr>
                <td colSpan={7} className="px-3 py-6 text-muted-foreground">
                  No products match these filters.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      {/* Print / PDF audit sheet */}
      <div className="report-print-area report-print-only">
        <h1>{settings.business_name} — Inventory Stock Snapshot</h1>
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
            brands={brands}
            onCategoriesChanged={setCategories}
            onBrandsChanged={setBrands}
            onCreated={() => {
              void load();
            }}
          />
          <ImportProductsDialog
            open={importOpen}
            onOpenChange={setImportOpen}
            onImported={() => {
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
            brands={brands}
            onBrandsChanged={setBrands}
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
