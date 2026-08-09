"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Minus, Plus, Printer, ScanBarcode, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { BarcodeScanModal } from "@/components/pos/barcode-scan-modal";
import { PaymentDialog } from "@/components/pos/payment-dialog";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SearchableCombobox } from "@/components/ui/searchable-combobox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useBarcodeScanner } from "@/hooks/use-barcode-scanner";
import { clientApi, toastError } from "@/lib/client-api";
import { printJobDocument } from "@/lib/print-job-document";
import type { Mechanic, Paginated, Product, Transaction } from "@/lib/types";
import { formatPeso } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useShop } from "@/components/shop/shop-context";

const PART_REMOVE_REASONS = [
  { value: "Wrong part selected", label: "Wrong part selected" },
  { value: "Customer changed mind", label: "Customer changed mind" },
  { value: "Duplicate entry", label: "Duplicate entry" },
  { value: "Not needed / not used", label: "Not needed / not used" },
  { value: "Wrong quantity", label: "Wrong quantity" },
  { value: "Damaged or defective", label: "Damaged or defective" },
  { value: "Other", label: "Other" },
] as const;

const LABOR_REMOVE_REASONS = [
  { value: "Entered by mistake", label: "Entered by mistake" },
  { value: "Duplicate entry", label: "Duplicate entry" },
  { value: "Not needed / cancelled", label: "Not needed / cancelled" },
  { value: "Wrong mechanic or fee", label: "Wrong mechanic or fee" },
  { value: "Other", label: "Other" },
] as const;

type RemoveTargetKind = "part" | "labor";

function truncateText(value: string, max = 32) {
  const trimmed = value.trim();
  if (trimmed.length <= max) return trimmed;
  return `${trimmed.slice(0, Math.max(0, max - 1))}…`;
}

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { settings } = useShop();
  const [tx, setTx] = useState<Transaction | null>(null);
  const [mechanics, setMechanics] = useState<Mechanic[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [productId, setProductId] = useState<string>("");
  const [barcodeQuery, setBarcodeQuery] = useState("");
  const [scanOpen, setScanOpen] = useState(false);
  const [qty, setQty] = useState("1");
  const [includeLabor, setIncludeLabor] = useState(false);
  const [partLaborService, setPartLaborService] = useState("");
  const [partLaborFee, setPartLaborFee] = useState("");
  const [partLaborInfo, setPartLaborInfo] = useState("");
  const [partMechanicId, setPartMechanicId] = useState("");
  const [serviceName, setServiceName] = useState("");
  const [laborFee, setLaborFee] = useState("");
  const [mechanicId, setMechanicId] = useState<string>("");
  const [payOpen, setPayOpen] = useState(false);
  const [removeKind, setRemoveKind] = useState<RemoveTargetKind | null>(null);
  const [removeLineId, setRemoveLineId] = useState<string | null>(null);
  const [removeReason, setRemoveReason] = useState<string | null>(null);
  const [removeOtherNote, setRemoveOtherNote] = useState("");
  const [removeBusy, setRemoveBusy] = useState(false);
  const [laborDetailId, setLaborDetailId] = useState<string | null>(null);
  const [partAddLaborId, setPartAddLaborId] = useState<string | null>(null);
  const [modalLaborService, setModalLaborService] = useState("");
  const [modalLaborFee, setModalLaborFee] = useState("");
  const [modalLaborInfo, setModalLaborInfo] = useState("");
  const [modalMechanicId, setModalMechanicId] = useState("");
  const [modalLaborBusy, setModalLaborBusy] = useState(false);

  const selectableProducts = useMemo(
    () => products.filter((p) => p.is_active && !p.deleted_at),
    [products],
  );
  const selectedProduct = useMemo(
    () => selectableProducts.find((p) => p.id === productId) ?? null,
    [selectableProducts, productId],
  );

  const removeTarget = useMemo(() => {
    if (!tx || !removeLineId || !removeKind) return null;
    if (removeKind === "part") {
      const line = tx.part_lines.find((l) => l.id === removeLineId);
      if (!line) return null;
      const product = products.find((p) => p.id === line.product_id);
      return { kind: "part" as const, line, product };
    }
    const line = tx.labor_lines.find((l) => l.id === removeLineId);
    if (!line) return null;
    const mechanic = mechanics.find((m) => m.id === line.mechanic_id);
    return { kind: "labor" as const, line, mechanic };
  }, [tx, removeLineId, removeKind, products, mechanics]);

  const removeReasons =
    removeKind === "labor" ? LABOR_REMOVE_REASONS : PART_REMOVE_REASONS;

  const laborDetail = useMemo(() => {
    if (!tx || !laborDetailId) return null;
    const line = tx.labor_lines.find((l) => l.id === laborDetailId);
    if (!line) return null;
    const mechanic = mechanics.find((m) => m.id === line.mechanic_id) ?? null;
    return { line, mechanic };
  }, [tx, laborDetailId, mechanics]);

  const partAddLaborTarget = useMemo(() => {
    if (!tx || !partAddLaborId) return null;
    const line = tx.part_lines.find((l) => l.id === partAddLaborId);
    if (!line) return null;
    const product = products.find((p) => p.id === line.product_id) ?? null;
    return { line, product };
  }, [tx, partAddLaborId, products]);

  function openRemovePart(lineId: string) {
    setRemoveKind("part");
    setRemoveLineId(lineId);
    setRemoveReason(null);
    setRemoveOtherNote("");
  }

  function openRemoveLabor(lineId: string) {
    setRemoveKind("labor");
    setRemoveLineId(lineId);
    setRemoveReason(null);
    setRemoveOtherNote("");
  }

  function openPartAddLabor(lineId: string) {
    if (tx?.status !== "IN_PROGRESS") return;
    const line = tx.part_lines.find((l) => l.id === lineId);
    if (!line) return;
    const product = products.find((p) => p.id === line.product_id);
    setPartAddLaborId(lineId);
    setModalLaborService(product ? `Install ${product.name}` : "");
    setModalLaborFee("");
    setModalLaborInfo("");
    setModalMechanicId("");
    setModalLaborBusy(false);
  }

  function closePartAddLabor() {
    setPartAddLaborId(null);
    setModalLaborService("");
    setModalLaborFee("");
    setModalLaborInfo("");
    setModalMechanicId("");
    setModalLaborBusy(false);
  }

  async function submitPartAddLabor() {
    if (!partAddLaborTarget) return;
    if (!modalMechanicId) {
      toast.error("Select a mechanic for this part’s labor");
      return;
    }
    if (!modalLaborFee || Number(modalLaborFee) < 0) {
      toast.error("Enter labor fee for this part");
      return;
    }
    const productName = partAddLaborTarget.product?.name ?? "part";
    const service = modalLaborService.trim() || `Install ${productName}`;
    const info = modalLaborInfo.trim();

    setModalLaborBusy(true);
    try {
      await clientApi(`/transactions/${id}/labor-lines`, {
        method: "POST",
        body: JSON.stringify({
          service_name: service,
          description: info || null,
          original_price: modalLaborFee,
          actual_price: modalLaborFee,
          mechanic_id: modalMechanicId,
        }),
      });
      toast.success(`Added labor for ${productName}`);
      closePartAddLabor();
      await load();
    } catch (err) {
      toastError(err);
      setModalLaborBusy(false);
    }
  }

  function applyProductSelection(product: Product) {
    setProductId(product.id);
    setBarcodeQuery(product.barcode);
    setPartLaborService((current) => {
      if (!includeLabor) return current;
      if (!current.trim() || current.startsWith("Install ")) {
        return `Install ${product.name}`;
      }
      return current;
    });
  }

  const load = useCallback(async () => {
    try {
      const [detail, mechs, prods] = await Promise.all([
        clientApi<Transaction>(`/transactions/${id}`),
        clientApi<Mechanic[]>("/mechanics"),
        clientApi<Paginated<Product>>("/products?page_size=100&lifecycle=all"),
      ]);
      setTx(detail);
      setMechanics(mechs.filter((m) => m.is_active));
      setProducts(prods.items);
      setProductId(
        (current) =>
          current ||
          prods.items.find((p) => p.is_active && !p.deleted_at)?.id ||
          "",
      );
    } catch (err) {
      toastError(err);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  function closeRemoveDialog() {
    setRemoveKind(null);
    setRemoveLineId(null);
    setRemoveReason(null);
    setRemoveOtherNote("");
    setRemoveBusy(false);
  }

  async function confirmRemoveLine() {
    if (!removeLineId || !removeKind || !removeReason) {
      toast.error(
        removeKind === "labor"
          ? "Select a reason to remove this labor"
          : "Select a reason to remove this part",
      );
      return;
    }
    const reason =
      removeReason === "Other"
        ? removeOtherNote.trim()
          ? `Other: ${removeOtherNote.trim()}`
          : ""
        : removeReason;
    if (!reason) {
      toast.error("Enter a short note for Other");
      return;
    }

    const path =
      removeKind === "labor"
        ? `/transactions/${id}/labor-lines/${removeLineId}/remove`
        : `/transactions/${id}/part-lines/${removeLineId}/remove`;

    setRemoveBusy(true);
    try {
      await clientApi(path, {
        method: "POST",
        body: JSON.stringify({ reason }),
      });
      toast.success(removeKind === "labor" ? "Labor removed" : "Part removed");
      closeRemoveDialog();
      await load();
    } catch (err) {
      toastError(err);
      setRemoveBusy(false);
    }
  }

  async function addPartByProduct(product: Product, quantity = Number(qty) || 1) {
    if (!Number.isInteger(quantity) || quantity < 1) {
      toast.error("Quantity must be a whole number of 1 or more");
      return;
    }
    const alreadyAdded =
      tx?.part_lines
        .filter((line) => line.product_id === product.id)
        .reduce((sum, line) => sum + line.quantity, 0) ?? 0;
    const available = Math.max(0, product.stock_qty - alreadyAdded);
    if (quantity > available) {
      toast.error(
        available > 0
          ? `Only ${available} more available for ${product.name}`
          : `${product.name} has no available stock`,
      );
      return;
    }
    if (includeLabor) {
      if (!partMechanicId) {
        toast.error("Select a mechanic for this part’s labor");
        return;
      }
      if (!partLaborFee || Number(partLaborFee) < 0) {
        toast.error("Enter labor fee for this part");
        return;
      }
    }

    try {
      await clientApi(`/transactions/${id}/part-lines`, {
        method: "POST",
        body: JSON.stringify({
          product_id: product.id,
          quantity,
        }),
      });

      if (includeLabor) {
        const service =
          partLaborService.trim() || `Install ${product.name}`;
        const info = partLaborInfo.trim();
        await clientApi(`/transactions/${id}/labor-lines`, {
          method: "POST",
          body: JSON.stringify({
            service_name: service,
            description: info || null,
            original_price: partLaborFee,
            actual_price: partLaborFee,
            mechanic_id: partMechanicId,
          }),
        });
        toast.success(`Added ${product.name} + labor`);
        setIncludeLabor(false);
        setPartLaborService("");
        setPartLaborFee("");
        setPartLaborInfo("");
        setPartMechanicId("");
      } else {
        toast.success(`Added ${product.name}`);
      }

      setQty("1");
      setBarcodeQuery("");
      setProductId("");
      await load();
    } catch (err) {
      toastError(err);
    }
  }

  async function resolveBarcode(code: string) {
    const trimmed = code.trim();
    if (!trimmed) return;

    let product =
      selectableProducts.find(
        (p) => p.barcode.toLowerCase() === trimmed.toLowerCase(),
      ) ??
      null;

    if (!product) {
      try {
        const res = await clientApi<Paginated<Product>>(
          `/products?q=${encodeURIComponent(trimmed)}&page_size=20`,
        );
        product =
          res.items.find((p) => p.barcode.toLowerCase() === trimmed.toLowerCase()) ??
          res.items[0] ??
          null;
        if (res.items.length) {
          setProducts((prev) => {
            const map = new Map(prev.map((p) => [p.id, p]));
            for (const item of res.items) map.set(item.id, item);
            return Array.from(map.values());
          });
        }
      } catch (err) {
        toastError(err);
        return;
      }
    }

    if (!product) {
      toast.error(`No product found for barcode “${trimmed}”`);
      return;
    }

    setProductId(product.id);
    setBarcodeQuery(product.barcode);
    await addPartByProduct(product, Number(qty) || 1);
  }

  useBarcodeScanner((code) => {
    if (
      tx?.status !== "IN_PROGRESS" ||
      payOpen ||
      scanOpen ||
      removeLineId ||
      laborDetailId ||
      partAddLaborId
    ) {
      return;
    }
    void resolveBarcode(code);
  });

  async function addPart() {
    if (!selectedProduct) {
      toast.error("Select or scan a product first");
      return;
    }
    await addPartByProduct(selectedProduct, Number(qty) || 1);
  }

  async function addLabor() {
    if (!serviceName.trim()) {
      toast.error("Enter a service name");
      return;
    }
    if (!laborFee || Number(laborFee) < 0) {
      toast.error("Enter labor fee");
      return;
    }
    try {
      await clientApi(`/transactions/${id}/labor-lines`, {
        method: "POST",
        body: JSON.stringify({
          service_name: serviceName.trim(),
          original_price: laborFee,
          actual_price: laborFee,
          mechanic_id: mechanicId || null,
        }),
      });
      toast.success(`Added labor: ${serviceName.trim()}`);
      setServiceName("");
      setLaborFee("");
      setMechanicId("");
      await load();
    } catch (err) {
      toastError(err);
    }
  }

  function printDoc(variant: "estimate" | "completion", doc: Transaction = tx!) {
    printJobDocument({
      tx: doc,
      products,
      mechanics,
      variant,
      businessName: settings.business_name,
      primaryColor: settings.primary_color,
    });
  }

  async function setStatus(status: string) {
    try {
      const updated = await clientApi<Transaction>(`/transactions/${id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      setTx(updated);
      if (status === "DONE") {
        toast.success("Job marked done — opening print…");
        printDoc("completion", updated);
      }
    } catch (err) {
      toastError(err);
    }
  }

  if (!tx) {
    return <p className="text-sm text-muted-foreground">Loading job…</p>;
  }

  const balance = Number(tx.totals?.balance_due ?? 0);

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="mb-1 flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-tight">
              {tx.plate_number?.trim() || tx.motorcycle_model || "Service job"}
            </h1>
            <Badge>{tx.status}</Badge>
            <Badge variant="secondary">{tx.document_number}</Badge>
          </div>
          <p className="text-sm text-muted-foreground">
            {[tx.customer_name, tx.customer_phone, tx.motorcycle_model]
              .filter((v) => v && String(v).trim())
              .join(" · ")}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {tx.status === "DONE" || tx.status === "PAID" ? (
            <Button
              type="button"
              variant="outline"
              className="min-h-11"
              onClick={() => printDoc("completion")}
            >
              <Printer className="mr-2 size-4" />
              Print completed job
            </Button>
          ) : null}
          {tx.status === "IN_PROGRESS" ? (
            <Button className="min-h-11" onClick={() => setStatus("DONE")}>
              Mark DONE
            </Button>
          ) : null}
          {tx.status === "DONE" ? (
            <>
              <Button
                variant="outline"
                className="min-h-11"
                onClick={() => setStatus("IN_PROGRESS")}
              >
                Reopen
              </Button>
              {balance > 0 ? (
                <Button className="min-h-11" onClick={() => setPayOpen(true)}>
                  {Number(tx.totals?.paid_total ?? 0) > 0
                    ? "Collect partial / balance"
                    : "Collect payment"}
                </Button>
              ) : null}
            </>
          ) : null}
          {tx.status === "IN_PROGRESS" && balance > 0 ? (
            <Button
              variant="secondary"
              className="min-h-11"
              onClick={() => setPayOpen(true)}
            >
              {Number(tx.totals?.paid_total ?? 0) > 0
                ? "Add partial payment"
                : "Collect deposit"}
            </Button>
          ) : null}
          {tx.status === "IN_PROGRESS" || tx.status === "DONE" ? (
            <Button
              variant="destructive"
              className="min-h-11"
              onClick={() => setStatus("CANCELLED")}
            >
              Cancel
            </Button>
          ) : null}
          {tx.status === "PAID" ? (
            <Link
              href={`/refunds?tx=${tx.id}`}
              className={cn(buttonVariants({ variant: "outline" }), "min-h-11")}
            >
              Refund
            </Link>
          ) : null}
        </div>
      </div>

      <div className="space-y-4">
        <div className="grid gap-4 lg:grid-cols-2">
          {tx.status === "IN_PROGRESS" ? (
            <section className="rounded-xl border bg-card p-4">
              <h2 className="mb-3 font-semibold">Add part</h2>
              <div className="space-y-2">
                <Label>Barcode / SKU</Label>
                <div className="flex gap-2">
                  <Input
                    className="min-h-11 font-mono"
                    data-barcode-capture="true"
                    autoComplete="off"
                    placeholder="Type barcode then Enter"
                    value={barcodeQuery}
                    onChange={(e) => setBarcodeQuery(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        void resolveBarcode(barcodeQuery);
                      }
                    }}
                  />
                  <Button
                    type="button"
                    variant="outline"
                    className="min-h-11 min-w-11"
                    onClick={() => setScanOpen(true)}
                    title="Open camera scanner"
                  >
                    <ScanBarcode className="size-5" />
                  </Button>
                </div>

                <Label>Or search product</Label>
                <SearchableCombobox
                  value={productId}
                  onValueChange={(next) => {
                    const product = selectableProducts.find((p) => p.id === next);
                    if (product) applyProductSelection(product);
                    else setProductId(next);
                  }}
                  placeholder="Search name or barcode…"
                  searchPlaceholder="Type product name or barcode…"
                  emptyText="No products match."
                  options={selectableProducts.map((p) => ({
                    value: p.id,
                    label: p.name,
                    description: `${p.barcode} · ${formatPeso(p.current_selling_price)} · stock ${p.stock_qty}`,
                    keywords: `${p.barcode} ${p.name}`,
                  }))}
                />

                <div className="space-y-2">
                  <Label htmlFor="job-part-quantity">Quantity</Label>
                  <div className="flex items-center gap-2">
                    <Button
                      type="button"
                      size="icon"
                      variant="outline"
                      className="size-11"
                      aria-label="Decrease quantity"
                      onClick={() =>
                        setQty((current) =>
                          String(Math.max(1, Number(current || 1) - 1)),
                        )
                      }
                      disabled={Number(qty) <= 1}
                    >
                      <Minus className="size-4" />
                    </Button>
                  <Input
                    id="job-part-quantity"
                    className="min-h-11 w-24 text-center tabular-nums"
                    type="number"
                    inputMode="numeric"
                    min={1}
                    max={selectedProduct?.stock_qty}
                    value={qty}
                    onChange={(e) => setQty(e.target.value)}
                    aria-label="Quantity"
                  />
                    <Button
                      type="button"
                      size="icon"
                      variant="outline"
                      className="size-11"
                      aria-label="Increase quantity"
                      onClick={() =>
                        setQty((current) =>
                          String(Number(current || 0) + 1),
                        )
                      }
                      disabled={
                        !!selectedProduct &&
                        Number(qty) >= selectedProduct.stock_qty
                      }
                    >
                      <Plus className="size-4" />
                    </Button>
                    {selectedProduct ? (
                      <span className="text-xs text-muted-foreground">
                        Available {selectedProduct.stock_qty}
                      </span>
                    ) : null}
                  </div>
                </div>

                <label className="flex min-h-11 items-center gap-2 rounded-lg border bg-muted/30 px-3 text-sm">
                  <input
                    type="checkbox"
                    checked={includeLabor}
                    onChange={(e) => {
                      const on = e.target.checked;
                      setIncludeLabor(on);
                      if (on && selectedProduct && !partLaborService.trim()) {
                        setPartLaborService(`Install ${selectedProduct.name}`);
                      }
                    }}
                  />
                  Also add mechanic labor for this part
                </label>

                {includeLabor ? (
                  <div className="space-y-2 rounded-lg border border-primary/20 bg-primary/5 p-3">
                    <div className="space-y-2">
                      <Label>Labor / service name</Label>
                      <Input
                        className="min-h-11"
                        value={partLaborService}
                        onChange={(e) => setPartLaborService(e.target.value)}
                        placeholder="e.g. Install oil filter"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Labor fee</Label>
                      <Input
                        className="min-h-11"
                        inputMode="decimal"
                        value={partLaborFee}
                        onChange={(e) => setPartLaborFee(e.target.value)}
                        placeholder="0.00"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Info (optional)</Label>
                      <Input
                        className="min-h-11"
                        value={partLaborInfo}
                        onChange={(e) => setPartLaborInfo(e.target.value)}
                        placeholder="Notes about this labor"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Mechanic</Label>
                      <SearchableCombobox
                        value={partMechanicId}
                        onValueChange={setPartMechanicId}
                        placeholder="Who did this labor?"
                        searchPlaceholder="Search mechanic…"
                        emptyText="No mechanics match."
                        options={mechanics.map((m) => ({
                          value: m.id,
                          label: `${m.nickname} (${m.full_name})`,
                          description: `Commission ${(Number(m.default_commission_rate) * 100).toFixed(0)}%`,
                          keywords: `${m.nickname} ${m.full_name}`,
                        }))}
                      />
                    </div>
                  </div>
                ) : null}

                <Button className="min-h-11 w-full" onClick={addPart}>
                  {includeLabor ? "Add part + labor" : "Add part"}
                </Button>
                <p className="text-xs text-muted-foreground">
                  Tip: barcode gun works on this page. Standalone labor (no part) is on the right.
                </p>
              </div>
            </section>
          ) : null}

          {tx.status === "IN_PROGRESS" ? (
            <section className="rounded-xl border bg-card p-4">
              <h2 className="mb-3 font-semibold">Add labor</h2>
              <div className="space-y-2">
                <p className="text-xs text-muted-foreground">
                  Standalone labor (e.g. diagnostics) without a part
                </p>
                <Input
                  className="min-h-11"
                  placeholder="Service name"
                  value={serviceName}
                  onChange={(e) => setServiceName(e.target.value)}
                />
                <Input
                  className="min-h-11"
                  placeholder="Labor fee"
                  inputMode="decimal"
                  value={laborFee}
                  onChange={(e) => setLaborFee(e.target.value)}
                />
                <Label>Mechanic</Label>
                <SearchableCombobox
                  value={mechanicId}
                  onValueChange={setMechanicId}
                  placeholder="Search mechanic…"
                  searchPlaceholder="Type nickname or name…"
                  emptyText="No mechanics match."
                  options={mechanics.map((m) => ({
                    value: m.id,
                    label: `${m.nickname} (${m.full_name})`,
                    description: `Commission ${(Number(m.default_commission_rate) * 100).toFixed(0)}%`,
                    keywords: `${m.nickname} ${m.full_name}`,
                  }))}
                />
                <Button className="min-h-11 w-full" onClick={addLabor}>
                  Add labor only
                </Button>
              </div>
            </section>
          ) : null}
        </div>

        <div className="grid gap-4 xl:grid-cols-2">
          <section className="rounded-xl border bg-card p-4">
            <h2 className="mb-3 font-semibold">Parts</h2>
            <ul className="space-y-2 text-sm">
              {tx.part_lines.map((line) => {
                const product = products.find((p) => p.id === line.product_id);
                const canRemove =
                  tx.status === "IN_PROGRESS" || tx.status === "DONE";
                const canAddLabor = tx.status === "IN_PROGRESS";
                return (
                  <li
                    key={line.id}
                    className={cn(
                      "flex justify-between gap-2 py-2 pl-3",
                      canAddLabor && "cursor-pointer rounded-lg hover:bg-muted/40",
                    )}
                    onClick={() => {
                      if (canAddLabor) openPartAddLabor(line.id);
                    }}
                    onKeyDown={(e) => {
                      if (!canAddLabor) return;
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        openPartAddLabor(line.id);
                      }
                    }}
                    role={canAddLabor ? "button" : undefined}
                    tabIndex={canAddLabor ? 0 : undefined}
                    title={canAddLabor ? "Tap to add labor for this part" : undefined}
                  >
                    <span className="min-w-0">
                      <span className="block truncate font-medium">
                        {product?.name ?? "Product"}
                      </span>
                      {product ? (
                        <span className="block truncate text-xs text-muted-foreground">
                          {product.barcode}
                        </span>
                      ) : null}
                      <span className="text-muted-foreground">
                        {" "}
                        × {line.quantity} @ {formatPeso(line.actual_selling_price)}
                      </span>
                      {canAddLabor ? (
                        <span className="mt-0.5 block text-xs text-primary">
                          Tap to add labor
                        </span>
                      ) : null}
                    </span>
                    <span className="flex shrink-0 items-center gap-2">
                      <span className="tabular-nums">
                        {formatPeso(Number(line.actual_selling_price) * line.quantity)}
                      </span>
                      {canRemove ? (
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="size-9 text-muted-foreground hover:text-destructive"
                          title="Remove part"
                          onClick={(e) => {
                            e.stopPropagation();
                            openRemovePart(line.id);
                          }}
                        >
                          <Trash2 className="size-4" />
                        </Button>
                      ) : null}
                    </span>
                  </li>
                );
              })}
              {!tx.part_lines.length ? (
                <li className="text-muted-foreground">No parts yet</li>
              ) : null}
            </ul>
            <p className="mt-3 flex justify-between border-t pt-3 text-sm font-medium">
              <span>Parts subtotal</span>
              <span className="tabular-nums">
                {formatPeso(tx.totals?.parts_total)}
              </span>
            </p>
          </section>

          <section className="rounded-xl border bg-card p-4">
            <h2 className="mb-3 font-semibold">Labor</h2>
            <ul className="space-y-2 text-sm">
              {tx.labor_lines.map((line) => {
                const mech = mechanics.find((m) => m.id === line.mechanic_id);
                const canRemove =
                  tx.status === "IN_PROGRESS" || tx.status === "DONE";
                const subtitle = [
                  mech?.nickname,
                  line.description?.trim() || null,
                ]
                  .filter(Boolean)
                  .join(" · ");
                return (
                  <li
                    key={line.id}
                    className="flex cursor-pointer justify-between gap-2 rounded-lg py-2 pl-3 hover:bg-muted/40"
                    onClick={() => setLaborDetailId(line.id)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setLaborDetailId(line.id);
                      }
                    }}
                    role="button"
                    tabIndex={0}
                    title="Tap to view full labor details"
                  >
                    <span className="min-w-0">
                      <span className="block font-medium">
                        {truncateText(line.service_name, 28)}
                      </span>
                      {subtitle ? (
                        <span className="block text-xs text-muted-foreground">
                          {truncateText(subtitle, 36)}
                        </span>
                      ) : null}
                    </span>
                    <span className="flex shrink-0 items-center gap-2">
                      <span className="tabular-nums">
                        {formatPeso(line.actual_price)}
                      </span>
                      {canRemove ? (
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="size-9 text-muted-foreground hover:text-destructive"
                          title="Remove labor"
                          onClick={(e) => {
                            e.stopPropagation();
                            openRemoveLabor(line.id);
                          }}
                        >
                          <Trash2 className="size-4" />
                        </Button>
                      ) : null}
                    </span>
                  </li>
                );
              })}
              {!tx.labor_lines.length ? (
                <li className="text-muted-foreground">No labor yet</li>
              ) : null}
            </ul>
            <p className="mt-3 flex justify-between border-t pt-3 text-sm font-medium">
              <span>Labor subtotal</span>
              <span className="tabular-nums">
                {formatPeso(tx.totals?.labor_total)}
              </span>
            </p>
          </section>
        </div>
      </div>

      <section className="rounded-xl border bg-card p-4">
        <h2 className="mb-3 font-semibold">Totals</h2>
        <p className="mb-3 text-xs text-muted-foreground">
          Partial payments are allowed — paid amount builds until balance due is
          ₱0.00, then the job becomes PAID. For a quote that is not saved as a
          job, use <strong>Estimate</strong> in the sidebar. Marking DONE prints
          a completion sheet automatically.
        </p>
        <div className="space-y-1 text-sm">
          <p className="flex justify-between">
            <span>Gross</span>
            <span className="tabular-nums">
              {formatPeso(tx.totals?.gross_total)}
            </span>
          </p>
          {Number(tx.totals?.discount_amount ?? 0) > 0 ? (
            <p className="flex justify-between text-muted-foreground">
              <span>Discount</span>
              <span className="tabular-nums">
                −{formatPeso(tx.totals?.discount_amount)}
              </span>
            </p>
          ) : null}
          <p className="flex justify-between font-medium">
            <span>Net</span>
            <span className="tabular-nums">
              {formatPeso(tx.totals?.net_total)}
            </span>
          </p>
          <p className="flex justify-between text-muted-foreground">
            <span>Paid</span>
            <span className="tabular-nums">
              {formatPeso(tx.totals?.paid_total)}
            </span>
          </p>
          <p className="flex justify-between border-t pt-2 text-base font-semibold">
            <span>Balance due</span>
            <span className="tabular-nums">
              {formatPeso(tx.totals?.balance_due)}
            </span>
          </p>
          {tx.payments?.length ? (
            <div className="mt-3 space-y-1.5 border-t pt-3">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Payments
              </p>
              <ul className="space-y-1.5">
                {tx.payments.map((payment) => (
                  <li
                    key={payment.id}
                    className="flex justify-between gap-3 text-muted-foreground"
                  >
                    <span className="min-w-0 truncate">
                      {payment.payment_method}
                      {payment.reference_no
                        ? ` · ${payment.reference_no}`
                        : ""}
                    </span>
                    <span className="shrink-0 tabular-nums text-foreground">
                      {formatPeso(payment.amount)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      </section>

      <BarcodeScanModal
        open={scanOpen}
        onOpenChange={setScanOpen}
        onScan={(code) => {
          void resolveBarcode(code);
        }}
      />

      <Dialog
        open={laborDetailId != null}
        onOpenChange={(open) => {
          if (!open) setLaborDetailId(null);
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Labor details</DialogTitle>
            <DialogDescription>
              Full information for this labor line.
            </DialogDescription>
          </DialogHeader>
          {laborDetail ? (
            <div className="space-y-3 text-sm">
              <div>
                <p className="text-xs text-muted-foreground">Service</p>
                <p className="font-medium break-words">
                  {laborDetail.line.service_name}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Info</p>
                <p className="break-words">
                  {laborDetail.line.description?.trim() || "—"}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Mechanic</p>
                <p>
                  {laborDetail.mechanic
                    ? `${laborDetail.mechanic.nickname} (${laborDetail.mechanic.full_name})`
                    : "—"}
                </p>
              </div>
              {laborDetail.line.mechanic_commission_rate != null ? (
                <div>
                  <p className="text-xs text-muted-foreground">Commission rate</p>
                  <p>
                    {(
                      Number(laborDetail.line.mechanic_commission_rate) * 100
                    ).toFixed(0)}
                    %
                  </p>
                </div>
              ) : null}
              <div>
                <p className="text-xs text-muted-foreground">Labor fee</p>
                <p className="tabular-nums font-medium">
                  {formatPeso(laborDetail.line.actual_price)}
                </p>
              </div>
            </div>
          ) : null}
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              className="min-h-11"
              onClick={() => setLaborDetailId(null)}
            >
              Close
            </Button>
            {laborDetail &&
            (tx.status === "IN_PROGRESS" || tx.status === "DONE") ? (
              <Button
                type="button"
                variant="destructive"
                className="min-h-11"
                onClick={() => {
                  const lineId = laborDetail.line.id;
                  setLaborDetailId(null);
                  openRemoveLabor(lineId);
                }}
              >
                Remove
              </Button>
            ) : null}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={partAddLaborId != null}
        onOpenChange={(open) => {
          if (!open) closePartAddLabor();
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Add labor for part</DialogTitle>
            <DialogDescription>
              {partAddLaborTarget
                ? `Add mechanic labor for ${partAddLaborTarget.product?.name ?? "this part"} × ${partAddLaborTarget.line.quantity}.`
                : "Add mechanic labor for this part."}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-2">
              <Label>Labor / service name</Label>
              <Input
                className="min-h-11"
                value={modalLaborService}
                onChange={(e) => setModalLaborService(e.target.value)}
                placeholder="e.g. Install oil filter"
              />
            </div>
            <div className="space-y-2">
              <Label>Labor fee</Label>
              <Input
                className="min-h-11"
                inputMode="decimal"
                value={modalLaborFee}
                onChange={(e) => setModalLaborFee(e.target.value)}
                placeholder="0.00"
              />
            </div>
            <div className="space-y-2">
              <Label>Info (optional)</Label>
              <Input
                className="min-h-11"
                value={modalLaborInfo}
                onChange={(e) => setModalLaborInfo(e.target.value)}
                placeholder="Notes about this labor"
              />
            </div>
            <div className="space-y-2">
              <Label>Mechanic</Label>
              <SearchableCombobox
                value={modalMechanicId}
                onValueChange={setModalMechanicId}
                placeholder="Who did this labor?"
                searchPlaceholder="Search mechanic…"
                emptyText="No mechanics match."
                options={mechanics.map((m) => ({
                  value: m.id,
                  label: `${m.nickname} (${m.full_name})`,
                  description: `Commission ${(Number(m.default_commission_rate) * 100).toFixed(0)}%`,
                  keywords: `${m.nickname} ${m.full_name}`,
                }))}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              className="min-h-11"
              disabled={modalLaborBusy}
              onClick={closePartAddLabor}
            >
              Cancel
            </Button>
            <Button
              type="button"
              className="min-h-11"
              disabled={modalLaborBusy}
              onClick={() => void submitPartAddLabor()}
            >
              {modalLaborBusy ? "Adding…" : "Add labor"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={removeLineId != null}
        onOpenChange={(open) => {
          if (!open) closeRemoveDialog();
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>
              {removeKind === "labor" ? "Remove labor" : "Remove part"}
            </DialogTitle>
            <DialogDescription>
              {removeTarget?.kind === "part"
                ? `Remove ${removeTarget.product?.name ?? "this part"} × ${removeTarget.line.quantity} from this job.`
                : removeTarget?.kind === "labor"
                  ? `Remove “${removeTarget.line.service_name}”${
                      removeTarget.mechanic
                        ? ` (${removeTarget.mechanic.nickname})`
                        : ""
                    } from this job.`
                  : "Select why this line should be removed."}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-2">
              <Label>Reason</Label>
              <Select
                value={removeReason}
                onValueChange={(value) => {
                  setRemoveReason(value);
                  if (value !== "Other") setRemoveOtherNote("");
                }}
                items={removeReasons.map((r) => ({
                  value: r.value,
                  label: r.label,
                }))}
              >
                <SelectTrigger className="min-h-11 w-full">
                  <SelectValue placeholder="Select a reason" />
                </SelectTrigger>
                <SelectContent align="start" className="w-[var(--anchor-width)]">
                  {removeReasons.map((reason) => (
                    <SelectItem key={reason.value} value={reason.value}>
                      {reason.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {removeReason === "Other" ? (
              <div className="space-y-2">
                <Label htmlFor="remove-other-note">Details</Label>
                <Input
                  id="remove-other-note"
                  className="min-h-11"
                  placeholder="Brief note"
                  value={removeOtherNote}
                  onChange={(e) => setRemoveOtherNote(e.target.value)}
                />
              </div>
            ) : null}
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              className="min-h-11"
              disabled={removeBusy}
              onClick={closeRemoveDialog}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="destructive"
              className="min-h-11"
              disabled={removeBusy || !removeReason}
              onClick={() => void confirmRemoveLine()}
            >
              {removeBusy
                ? "Removing…"
                : removeKind === "labor"
                  ? "Remove labor"
                  : "Remove part"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <PaymentDialog
        open={payOpen}
        onOpenChange={setPayOpen}
        balanceDue={balance}
        allowPartial
        onPaid={async (payment) => {
          await clientApi(`/transactions/${id}/payments`, {
            method: "POST",
            body: JSON.stringify(payment),
          });
          const amount = Number(payment.amount);
          const remaining = Math.max(0, balance - amount);
          if (remaining <= 0.009) {
            toast.success("Payment complete — job marked PAID");
          } else {
            toast.success(
              `Partial payment recorded · remaining ${formatPeso(remaining)}`,
            );
          }
          await load();
          router.refresh();
        }}
      />
    </div>
  );
}
