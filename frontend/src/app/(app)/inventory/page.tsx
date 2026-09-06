"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ChevronLeft,
  ChevronRight,
  FileDown,
  FileSpreadsheet,
  Plus,
  Printer,
  RotateCcw,
  Trash2,
  Upload,
} from "lucide-react";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { clientApi, toastError } from "@/lib/client-api";
import type {
  Paginated,
  Product,
  ProductCategory,
  ProductDeletionImpact,
} from "@/lib/types";
import { formatPeso } from "@/lib/types";

type ProductLifecycle = "active" | "disabled" | "deleted" | "all";

const PAGE_SIZE_OPTIONS = [10, 100, 500] as const;
type PageSize = (typeof PAGE_SIZE_OPTIONS)[number];

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
  const [printItems, setPrintItems] = useState<Product[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<PageSize>(10);
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
  const [exportingExcel, setExportingExcel] = useState(false);
  const [printBusy, setPrintBusy] = useState(false);

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

  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const rangeStart = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const rangeEnd = Math.min(page * pageSize, total);

  const printTotalUnits = useMemo(
    () => printItems.reduce((sum, p) => sum + p.stock_qty, 0),
    [printItems],
  );

  const printLowStockCount = useMemo(
    () => printItems.filter((p) => p.stock_qty <= p.min_stock_threshold).length,
    [printItems],
  );

  function buildFilterParams(extra?: Record<string, string>) {
    const params = new URLSearchParams(extra);
    if (q.trim()) params.set("q", q.trim());
    if (categoryId !== "all") params.set("category_id", categoryId);
    if (brand !== "all") params.set("brand", brand);
    params.set("lifecycle", lifecycle);
    return params;
  }

  async function load(targetPage = page, size = pageSize) {
    try {
      const params = buildFilterParams({
        page: String(targetPage),
        page_size: String(size),
      });
      const [products, cats, brandList] = await Promise.all([
        clientApi<Paginated<Product>>(`/products?${params}`),
        clientApi<ProductCategory[]>("/categories"),
        clientApi<string[]>("/products/brands"),
      ]);
      const maxPage = Math.max(1, Math.ceil(products.total / size));
      if (products.total > 0 && targetPage > maxPage) {
        setPage(maxPage);
        return;
      }
      setItems(products.items);
      setTotal(products.total);
      setCategories(cats);
      setBrands(brandList);
      setSnapshotAt(new Date());
    } catch (err) {
      toastError(err);
    }
  }

  async function fetchAllFilteredProducts(): Promise<Product[]> {
    const fetchSize = 500;
    let current = 1;
    let collected: Product[] = [];
    let expected = Infinity;

    while (collected.length < expected) {
      const params = buildFilterParams({
        page: String(current),
        page_size: String(fetchSize),
      });
      const res = await clientApi<Paginated<Product>>(`/products?${params}`);
      expected = res.total;
      collected = collected.concat(res.items);
      if (!res.items.length || collected.length >= expected) break;
      current += 1;
    }

    return collected;
  }

  useEffect(() => {
    void load(page, pageSize);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, pageSize, categoryId, brand, lifecycle]);

  function changePageSize(next: PageSize) {
    setPageSize(next);
    setPage(1);
  }

  function resetToFirstPageAndLoad() {
    if (page !== 1) {
      setPage(1);
    } else {
      void load(1);
    }
  }

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

  async function exportExcel() {
    setExportingExcel(true);
    try {
      const params = buildFilterParams();
      const res = await fetch(`/api/proxy/products/export?${params}`);
      if (!res.ok) {
        let detail = res.statusText;
        try {
          const data = await res.json();
          detail =
            typeof data.detail === "string" ? data.detail : res.statusText;
        } catch {
          /* ignore */
        }
        throw new Error(detail || "Failed to export inventory");
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${fileSafeName(settings.business_name)}-inventory-export.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success("Inventory exported");
    } catch (err) {
      toastError(err);
    } finally {
      setExportingExcel(false);
    }
  }

  async function exportPdf() {
    setPrintBusy(true);
    try {
      const all = await fetchAllFilteredProducts();
      if (!all.length) {
        toast.error("No products to export");
        return;
      }
      const stamped = new Date();
      setPrintItems(all);
      setSnapshotAt(stamped);
      const previous = document.title;
      document.title = `${fileSafeName(settings.business_name)}-Inventory-${formatSnapshotFileStamp(stamped)}`;
      // Wait for full inventory rows to paint before opening the print dialog
      window.setTimeout(() => {
        window.print();
        document.title = previous;
        setPrintBusy(false);
      }, 100);
    } catch (err) {
      toastError(err);
      setPrintBusy(false);
    }
  }

  async function exportBarcodes() {
    setPrintBusy(true);
    try {
      const all = await fetchAllFilteredProducts();
      if (!all.length) {
        toast.error("No products to export");
        return;
      }
      printBarcodeLabels(
        all.map((p) => ({
          barcode: p.barcode,
          name: p.name,
        })),
        1,
      );
    } catch (err) {
      toastError(err);
    } finally {
      setPrintBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Inventory</h1>
          <p className="text-sm text-muted-foreground">
            Search and filter by brand, category, name, or barcode — export Excel
            (import format), PDF, or barcode labels for the full filtered list
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
            disabled={exportingExcel || total === 0}
            onClick={() => void exportExcel()}
          >
            <FileSpreadsheet className="size-4" />
            {exportingExcel ? "Exporting…" : "Export Excel"}
          </Button>
          <Button
            className="min-h-11 gap-2"
            variant="outline"
            disabled={printBusy || total === 0}
            onClick={() => void exportBarcodes()}
          >
            <Printer className="size-4" />
            Export barcodes
          </Button>
          <Button
            className="min-h-11 gap-2"
            variant="outline"
            disabled={printBusy || total === 0}
            onClick={() => void exportPdf()}
          >
            <FileDown className="size-4" />
            {printBusy ? "Preparing…" : "Export PDF"}
          </Button>
        </div>
      </div>

      <div className="no-print flex flex-col gap-2 lg:flex-row">
        <Input
          className="min-h-11"
          placeholder="Search name, barcode, or brand"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") resetToFirstPageAndLoad();
          }}
        />
        <SearchableCombobox
          className="lg:w-48"
          value={brand}
          onValueChange={(value) => {
            setBrand(value);
            setPage(1);
          }}
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
          onValueChange={(value) => {
            setCategoryId(value);
            setPage(1);
          }}
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
          onValueChange={(value) => {
            setLifecycle(value as ProductLifecycle);
            setPage(1);
          }}
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
        <Button className="min-h-11" onClick={resetToFirstPageAndLoad}>
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
                <td className="px-3 py-3 font-medium">
                  <div>{p.name}</div>
                  {(p.applicable_motorcycle_models ?? []).length > 0 ? (
                    <p className="mt-1 text-xs font-normal text-muted-foreground">
                      Fits:{" "}
                      {(p.applicable_motorcycle_models ?? [])
                        .map((m) => m.display_name)
                        .join(", ")}
                    </p>
                  ) : null}
                </td>
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

      <div className="no-print flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-4">
          <p className="text-sm text-muted-foreground">
            {total === 0
              ? "No products"
              : `Showing ${rangeStart}–${rangeEnd} of ${total}`}
          </p>
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">Rows</span>
            <Select
              value={String(pageSize)}
              onValueChange={(value) => {
                if (!value) return;
                changePageSize(Number(value) as PageSize);
              }}
            >
              <SelectTrigger className="h-11 w-[5.5rem]">
                <SelectValue>{String(pageSize)}</SelectValue>
              </SelectTrigger>
              <SelectContent>
                {PAGE_SIZE_OPTIONS.map((size) => (
                  <SelectItem key={size} value={String(size)}>
                    {size}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            className="min-h-11 gap-1"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            <ChevronLeft className="size-4" />
            Previous
          </Button>
          <span className="min-w-24 text-center text-sm tabular-nums text-muted-foreground">
            Page {page} of {totalPages}
          </span>
          <Button
            variant="outline"
            className="min-h-11 gap-1"
            disabled={page >= totalPages || total === 0}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
            <ChevronRight className="size-4" />
          </Button>
        </div>
      </div>

      {/* Print / PDF audit sheet — uses full filtered inventory, not just current page */}
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
          <strong>SKUs listed:</strong> {printItems.length}
          {" · "}
          <strong>System units:</strong> {printTotalUnits}
          {" · "}
          <strong>Low stock:</strong> {printLowStockCount}
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
            {printItems.map((p, index) => (
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
