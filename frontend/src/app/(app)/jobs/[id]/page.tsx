"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ScanBarcode, Trash2 } from "lucide-react";
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
import type { Mechanic, Paginated, Product, Transaction } from "@/lib/types";
import { formatPeso } from "@/lib/types";
import { cn } from "@/lib/utils";

const PART_REMOVE_REASONS = [
  { value: "Wrong part selected", label: "Wrong part selected" },
  { value: "Customer changed mind", label: "Customer changed mind" },
  { value: "Duplicate entry", label: "Duplicate entry" },
  { value: "Not needed / not used", label: "Not needed / not used" },
  { value: "Wrong quantity", label: "Wrong quantity" },
  { value: "Damaged or defective", label: "Damaged or defective" },
  { value: "Other", label: "Other" },
] as const;

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
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
  const [removeLineId, setRemoveLineId] = useState<string | null>(null);
  const [removeReason, setRemoveReason] = useState<string | null>(null);
  const [removeOtherNote, setRemoveOtherNote] = useState("");
  const [removeBusy, setRemoveBusy] = useState(false);

  const selectedProduct = useMemo(
    () => products.find((p) => p.id === productId) ?? null,
    [products, productId],
  );

  const removeTarget = useMemo(() => {
    if (!tx || !removeLineId) return null;
    const line = tx.part_lines.find((l) => l.id === removeLineId);
    if (!line) return null;
    const product = products.find((p) => p.id === line.product_id);
    return { line, product };
  }, [tx, removeLineId, products]);

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
        clientApi<Paginated<Product>>("/products?page_size=100"),
      ]);
      setTx(detail);
      setMechanics(mechs.filter((m) => m.is_active));
      setProducts(prods.items);
      setProductId((current) => current || prods.items[0]?.id || "");
    } catch (err) {
      toastError(err);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  function closeRemoveDialog() {
    setRemoveLineId(null);
    setRemoveReason(null);
    setRemoveOtherNote("");
    setRemoveBusy(false);
  }

  async function confirmRemovePart() {
    if (!removeLineId || !removeReason) {
      toast.error("Select a reason to remove this part");
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

    setRemoveBusy(true);
    try {
      await clientApi(`/transactions/${id}/part-lines/${removeLineId}/remove`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      });
      toast.success("Part removed");
      closeRemoveDialog();
      await load();
    } catch (err) {
      toastError(err);
      setRemoveBusy(false);
    }
  }

  async function addPartByProduct(product: Product, quantity = Number(qty) || 1) {
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
      products.find((p) => p.barcode.toLowerCase() === trimmed.toLowerCase()) ??
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
    if (tx?.status !== "IN_PROGRESS" || payOpen || scanOpen || removeLineId) return;
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

  async function setStatus(status: string) {
    try {
      const updated = await clientApi<Transaction>(`/transactions/${id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      setTx(updated);
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
              <Button className="min-h-11" onClick={() => setPayOpen(true)}>
                Collect payment
              </Button>
            </>
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

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-xl border bg-card p-4">
          <h2 className="mb-3 font-semibold">Parts</h2>
          <ul className="mb-4 space-y-2 text-sm">
            {tx.part_lines.map((line) => {
              const product = products.find((p) => p.id === line.product_id);
              const canRemove =
                tx.status === "IN_PROGRESS" || tx.status === "DONE";
              return (
                <li key={line.id} className="flex justify-between gap-2 border-b py-2">
                  <span className="min-w-0">
                    <span className="font-medium">
                      {product?.name ?? "Product"}
                    </span>
                    {product ? (
                      <span className="block text-xs text-muted-foreground">
                        {product.barcode}
                      </span>
                    ) : null}
                    <span className="text-muted-foreground"> × {line.quantity}</span>
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
                        onClick={() => {
                          setRemoveLineId(line.id);
                          setRemoveReason(null);
                          setRemoveOtherNote("");
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
          {tx.status === "IN_PROGRESS" ? (
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
                  const product = products.find((p) => p.id === next);
                  if (product) applyProductSelection(product);
                  else setProductId(next);
                }}
                placeholder="Search name or barcode…"
                searchPlaceholder="Type product name or barcode…"
                emptyText="No products match."
                options={products.map((p) => ({
                  value: p.id,
                  label: p.name,
                  description: `${p.barcode} · ${formatPeso(p.current_selling_price)} · stock ${p.stock_qty}`,
                  keywords: `${p.barcode} ${p.name}`,
                }))}
              />

              <div className="flex gap-2">
                <Input
                  className="min-h-11"
                  type="number"
                  min={1}
                  value={qty}
                  onChange={(e) => setQty(e.target.value)}
                  aria-label="Quantity"
                />
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
          ) : null}
        </section>

        <section className="rounded-xl border bg-card p-4">
          <h2 className="mb-3 font-semibold">Labor</h2>
          <ul className="mb-4 space-y-2 text-sm">
            {tx.labor_lines.map((line) => {
              const mech = mechanics.find((m) => m.id === line.mechanic_id);
              return (
                <li key={line.id} className="flex justify-between gap-2 border-b py-2">
                  <span>
                    <span className="font-medium">{line.service_name}</span>
                    {mech ? (
                      <span className="block text-xs text-muted-foreground">
                        {mech.nickname}
                        {line.description ? ` · ${line.description}` : ""}
                      </span>
                    ) : line.description ? (
                      <span className="block text-xs text-muted-foreground">
                        {line.description}
                      </span>
                    ) : null}
                  </span>
                  <span className="tabular-nums">{formatPeso(line.actual_price)}</span>
                </li>
              );
            })}
            {!tx.labor_lines.length ? (
              <li className="text-muted-foreground">No labor yet</li>
            ) : null}
          </ul>
          {tx.status === "IN_PROGRESS" ? (
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
          ) : null}
        </section>
      </div>

      <section className="rounded-xl border bg-card p-4">
        <h2 className="mb-3 font-semibold">Totals breakdown</h2>

        <div className="space-y-4 text-sm">
          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Parts
            </p>
            <ul className="space-y-1.5">
              {tx.part_lines.map((line) => {
                const product = products.find((p) => p.id === line.product_id);
                const lineTotal =
                  Number(line.actual_selling_price) * line.quantity;
                return (
                  <li
                    key={line.id}
                    className="flex justify-between gap-3 border-b border-border/60 pb-1.5"
                  >
                    <span className="min-w-0">
                      <span className="font-medium">
                        {product?.name ?? "Product"}
                      </span>
                      <span className="text-muted-foreground">
                        {" "}
                        × {line.quantity} @ {formatPeso(line.actual_selling_price)}
                      </span>
                    </span>
                    <span className="shrink-0 tabular-nums">
                      {formatPeso(lineTotal)}
                    </span>
                  </li>
                );
              })}
              {!tx.part_lines.length ? (
                <li className="text-muted-foreground">No parts</li>
              ) : null}
            </ul>
            <p className="mt-2 flex justify-between font-medium">
              <span>Parts subtotal</span>
              <span className="tabular-nums">
                {formatPeso(tx.totals?.parts_total)}
              </span>
            </p>
          </div>

          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Labor
            </p>
            <ul className="space-y-1.5">
              {tx.labor_lines.map((line) => {
                const mech = mechanics.find((m) => m.id === line.mechanic_id);
                return (
                  <li
                    key={line.id}
                    className="flex justify-between gap-3 border-b border-border/60 pb-1.5"
                  >
                    <span className="min-w-0">
                      <span className="font-medium">{line.service_name}</span>
                      {mech ? (
                        <span className="block text-xs text-muted-foreground">
                          {mech.nickname}
                          {line.description ? ` · ${line.description}` : ""}
                        </span>
                      ) : line.description ? (
                        <span className="block text-xs text-muted-foreground">
                          {line.description}
                        </span>
                      ) : null}
                    </span>
                    <span className="shrink-0 tabular-nums">
                      {formatPeso(line.actual_price)}
                    </span>
                  </li>
                );
              })}
              {!tx.labor_lines.length ? (
                <li className="text-muted-foreground">No labor</li>
              ) : null}
            </ul>
            <p className="mt-2 flex justify-between font-medium">
              <span>Labor subtotal</span>
              <span className="tabular-nums">
                {formatPeso(tx.totals?.labor_total)}
              </span>
            </p>
          </div>

          <div className="space-y-1 border-t pt-3">
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
            <p className="flex justify-between text-base font-semibold">
              <span>Balance due</span>
              <span className="tabular-nums">
                {formatPeso(tx.totals?.balance_due)}
              </span>
            </p>
          </div>
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
        open={removeLineId != null}
        onOpenChange={(open) => {
          if (!open) closeRemoveDialog();
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Remove part</DialogTitle>
            <DialogDescription>
              {removeTarget
                ? `Remove ${removeTarget.product?.name ?? "this part"} × ${removeTarget.line.quantity} from this job.`
                : "Select why this part should be removed."}
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
                items={PART_REMOVE_REASONS.map((r) => ({
                  value: r.value,
                  label: r.label,
                }))}
              >
                <SelectTrigger className="min-h-11 w-full">
                  <SelectValue placeholder="Select a reason" />
                </SelectTrigger>
                <SelectContent align="start" className="w-[var(--anchor-width)]">
                  {PART_REMOVE_REASONS.map((reason) => (
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
              onClick={() => void confirmRemovePart()}
            >
              {removeBusy ? "Removing…" : "Remove part"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <PaymentDialog
        open={payOpen}
        onOpenChange={setPayOpen}
        balanceDue={balance}
        onPaid={async (payment) => {
          await clientApi(`/transactions/${id}/payments`, {
            method: "POST",
            body: JSON.stringify(payment),
          });
          await load();
          router.refresh();
        }}
      />
    </div>
  );
}
