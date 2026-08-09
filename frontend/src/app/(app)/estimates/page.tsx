"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Printer, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { MotorcycleModelField } from "@/components/jobs/motorcycle-model-field";
import { useShop } from "@/components/shop/shop-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SearchableCombobox } from "@/components/ui/searchable-combobox";
import { Textarea } from "@/components/ui/textarea";
import { clientApi, toastError } from "@/lib/client-api";
import {
  createEmptyEstimate,
  estimateId,
  estimateTotals,
  printEstimateDocument,
  type EstimateDraft,
} from "@/lib/print-estimate";
import type { Paginated, Product } from "@/lib/types";
import { formatPeso } from "@/lib/types";

export default function EstimatePage() {
  const { settings } = useShop();
  const [products, setProducts] = useState<Product[]>([]);
  const [draft, setDraft] = useState<EstimateDraft>(() => createEmptyEstimate());
  const [productId, setProductId] = useState("");
  const [partQty, setPartQty] = useState("1");
  const [serviceName, setServiceName] = useState("");
  const [serviceDesc, setServiceDesc] = useState("");
  const [laborFee, setLaborFee] = useState("");

  const loadProducts = useCallback(async () => {
    try {
      const data = await clientApi<Paginated<Product>>(
        "/products?page_size=100",
      );
      setProducts(data.items.filter((p) => p.is_active));
    } catch (err) {
      toastError(err);
    }
  }, []);

  useEffect(() => {
    void loadProducts();
  }, [loadProducts]);

  const totals = useMemo(() => estimateTotals(draft), [draft]);

  const productOptions = useMemo(
    () =>
      products.map((p) => ({
        value: p.id,
        label: `${p.name}${p.barcode ? ` · ${p.barcode}` : ""} · ${formatPeso(p.current_selling_price)}`,
      })),
    [products],
  );

  function updateField<K extends keyof EstimateDraft>(
    key: K,
    value: EstimateDraft[K],
  ) {
    setDraft((prev) => ({ ...prev, [key]: value }));
  }

  function addPart() {
    const product = products.find((p) => p.id === productId);
    if (!product) {
      toast.error("Select a part");
      return;
    }
    const qty = Number(partQty);
    if (!Number.isInteger(qty) || qty < 1) {
      toast.error("Quantity must be a whole number ≥ 1");
      return;
    }
    const unit = Number(product.current_selling_price);
    setDraft((prev) => {
      const existing = prev.parts.find((line) => line.product_id === product.id);
      if (existing) {
        return {
          ...prev,
          parts: prev.parts.map((line) =>
            line.product_id === product.id
              ? { ...line, quantity: line.quantity + qty }
              : line,
          ),
        };
      }
      return {
        ...prev,
        parts: [
          ...prev.parts,
          {
            id: estimateId(),
            product_id: product.id,
            name: product.name,
            barcode: product.barcode,
            quantity: qty,
            unit_price: unit,
          },
        ],
      };
    });
    setProductId("");
    setPartQty("1");
  }

  function addLabor() {
    const name = serviceName.trim();
    const fee = Number(laborFee);
    if (!name) {
      toast.error("Enter a service name");
      return;
    }
    if (!Number.isFinite(fee) || fee < 0) {
      toast.error("Enter a valid labor fee");
      return;
    }
    setDraft((prev) => ({
      ...prev,
      labor: [
        ...prev.labor,
        {
          id: estimateId(),
          service_name: name,
          description: serviceDesc.trim() || null,
          fee,
        },
      ],
    }));
    setServiceName("");
    setServiceDesc("");
    setLaborFee("");
  }

  function clearAll() {
    setDraft(createEmptyEstimate());
    setProductId("");
    setPartQty("1");
    setServiceName("");
    setServiceDesc("");
    setLaborFee("");
    toast.success("Estimate cleared");
  }

  function print() {
    printEstimateDocument({
      draft,
      businessName: settings.business_name,
      primaryColor: settings.primary_color,
    });
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Estimate</h1>
          <p className="text-sm text-muted-foreground">
            Quote parts and labor for a customer. Nothing is saved — print only.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="outline"
            className="min-h-11"
            onClick={clearAll}
          >
            Clear
          </Button>
          <Button type="button" className="min-h-11 gap-2" onClick={print}>
            <Printer className="size-4" />
            Print estimate
          </Button>
        </div>
      </div>

      <section className="rounded-xl border bg-card p-4">
        <h2 className="mb-3 font-semibold">Customer / bike (optional)</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="est-customer">Customer</Label>
            <Input
              id="est-customer"
              className="min-h-11"
              value={draft.customer_name}
              onChange={(e) => updateField("customer_name", e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="est-phone">Phone</Label>
            <Input
              id="est-phone"
              className="min-h-11"
              value={draft.customer_phone}
              onChange={(e) => updateField("customer_phone", e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <MotorcycleModelField
              id="est-model"
              value={draft.motorcycle_model}
              onChange={(motorcycle_model) =>
                updateField("motorcycle_model", motorcycle_model)
              }
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="est-plate">Plate</Label>
            <Input
              id="est-plate"
              className="min-h-11"
              value={draft.plate_number}
              onChange={(e) => updateField("plate_number", e.target.value)}
            />
          </div>
          <div className="space-y-2 sm:col-span-2">
            <Label htmlFor="est-notes">Notes / complaint</Label>
            <Textarea
              id="est-notes"
              value={draft.diagnosis_notes}
              onChange={(e) => updateField("diagnosis_notes", e.target.value)}
            />
          </div>
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-2">
        <section className="rounded-xl border bg-card p-4">
          <h2 className="mb-3 font-semibold">Add part</h2>
          <div className="space-y-3">
            <div className="space-y-2">
              <Label>Product</Label>
              <SearchableCombobox
                value={productId}
                onValueChange={setProductId}
                placeholder="Search part…"
                searchPlaceholder="Name or barcode…"
                emptyText="No products found."
                options={productOptions}
              />
            </div>
            <div className="flex flex-wrap gap-2">
              <Input
                className="min-h-11 w-24"
                inputMode="numeric"
                value={partQty}
                onChange={(e) => setPartQty(e.target.value)}
                aria-label="Quantity"
              />
              <Button type="button" className="min-h-11" onClick={addPart}>
                Add part
              </Button>
            </div>
          </div>

          <ul className="mt-4 divide-y border-t">
            {draft.parts.map((line) => (
              <li
                key={line.id}
                className="flex items-start justify-between gap-3 py-3 text-sm"
              >
                <div className="min-w-0">
                  <p className="font-medium">{line.name}</p>
                  <p className="text-muted-foreground">
                    x {line.quantity} @ {formatPeso(line.unit_price)}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <span className="tabular-nums font-medium">
                    {formatPeso(line.unit_price * line.quantity)}
                  </span>
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    className="size-9"
                    onClick={() =>
                      setDraft((prev) => ({
                        ...prev,
                        parts: prev.parts.filter((p) => p.id !== line.id),
                      }))
                    }
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </div>
              </li>
            ))}
            {!draft.parts.length ? (
              <li className="py-4 text-sm text-muted-foreground">No parts yet</li>
            ) : null}
          </ul>
        </section>

        <section className="rounded-xl border bg-card p-4">
          <h2 className="mb-3 font-semibold">Add labor / service</h2>
          <div className="space-y-3">
            <div className="space-y-2">
              <Label htmlFor="est-service">Service</Label>
              <Input
                id="est-service"
                className="min-h-11"
                placeholder="e.g. Oil change, brake job"
                value={serviceName}
                onChange={(e) => setServiceName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="est-fee">Fee</Label>
              <Input
                id="est-fee"
                className="min-h-11"
                inputMode="decimal"
                placeholder="0.00"
                value={laborFee}
                onChange={(e) => setLaborFee(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="est-desc">Description (optional)</Label>
              <Input
                id="est-desc"
                className="min-h-11"
                value={serviceDesc}
                onChange={(e) => setServiceDesc(e.target.value)}
              />
            </div>
            <Button type="button" className="min-h-11" onClick={addLabor}>
              Add service
            </Button>
          </div>

          <ul className="mt-4 divide-y border-t">
            {draft.labor.map((line) => (
              <li
                key={line.id}
                className="flex items-start justify-between gap-3 py-3 text-sm"
              >
                <div className="min-w-0">
                  <p className="font-medium">{line.service_name}</p>
                  {line.description ? (
                    <p className="text-muted-foreground">{line.description}</p>
                  ) : null}
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <span className="tabular-nums font-medium">
                    {formatPeso(line.fee)}
                  </span>
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    className="size-9"
                    onClick={() =>
                      setDraft((prev) => ({
                        ...prev,
                        labor: prev.labor.filter((l) => l.id !== line.id),
                      }))
                    }
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </div>
              </li>
            ))}
            {!draft.labor.length ? (
              <li className="py-4 text-sm text-muted-foreground">
                No services yet
              </li>
            ) : null}
          </ul>
        </section>
      </div>

      <section className="rounded-xl border bg-card p-4">
        <h2 className="mb-3 font-semibold">Totals</h2>
        <dl className="space-y-2 text-sm">
          <div className="flex justify-between gap-3">
            <dt className="text-muted-foreground">Parts</dt>
            <dd className="tabular-nums font-medium">
              {formatPeso(totals.parts_total)}
            </dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt className="text-muted-foreground">Labor</dt>
            <dd className="tabular-nums font-medium">
              {formatPeso(totals.labor_total)}
            </dd>
          </div>
          <div className="flex justify-between gap-3 border-t pt-2 text-base font-semibold">
            <dt>Estimated total</dt>
            <dd className="tabular-nums">{formatPeso(totals.net_total)}</dd>
          </div>
        </dl>
      </section>
    </div>
  );
}
