"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { toast } from "sonner";

import { useBranch } from "@/components/branch/branch-context";
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
import type { Paginated, Product, StockTransfer } from "@/lib/types";

export default function TransfersPage() {
  const { branches, activeBranch } = useBranch();
  const [items, setItems] = useState<StockTransfer[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    from_branch_id: "",
    to_branch_id: "",
    product_id: "",
    quantity: "1",
    notes: "",
  });

  const load = useCallback(async () => {
    try {
      const [transfers, prods] = await Promise.all([
        clientApi<StockTransfer[] | Paginated<StockTransfer>>("/transfers"),
        clientApi<Paginated<Product>>("/products?page_size=100"),
      ]);
      setItems(Array.isArray(transfers) ? transfers : transfers.items);
      setProducts(prods.items);
    } catch (err) {
      toastError(err);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (activeBranch && !form.from_branch_id) {
      setForm((f) => ({ ...f, from_branch_id: activeBranch.id }));
    }
  }, [activeBranch, form.from_branch_id]);

  function branchName(id: string) {
    return branches.find((b) => b.id === id)?.name ?? id.slice(0, 8);
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (form.from_branch_id === form.to_branch_id) {
      toast.error("Source and destination branches must differ");
      return;
    }
    setBusy(true);
    try {
      await clientApi("/transfers", {
        method: "POST",
        body: JSON.stringify({
          from_branch_id: form.from_branch_id,
          to_branch_id: form.to_branch_id,
          notes: form.notes.trim() || null,
          lines: [
            {
              product_id: form.product_id,
              quantity: Number(form.quantity),
            },
          ],
        }),
      });
      toast.success("Transfer completed");
      setOpen(false);
      await load();
    } catch (err) {
      toastError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Stock transfers
          </h1>
          <p className="text-sm text-muted-foreground">
            Move inventory between branches (ADMIN)
          </p>
        </div>
        <Button
          className="min-h-11 gap-2"
          onClick={() => {
            setForm({
              from_branch_id: activeBranch?.id ?? "",
              to_branch_id: "",
              product_id: products[0]?.id ?? "",
              quantity: "1",
              notes: "",
            });
            setOpen(true);
          }}
        >
          <Plus className="size-4" />
          New transfer
        </Button>
      </div>

      <div className="overflow-x-auto rounded-xl border bg-card">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="border-b bg-muted/40">
            <tr>
              <th className="px-3 py-3">Document</th>
              <th className="px-3 py-3">From</th>
              <th className="px-3 py-3">To</th>
              <th className="px-3 py-3">Lines</th>
              <th className="px-3 py-3">When</th>
            </tr>
          </thead>
          <tbody>
            {items.map((t) => (
              <tr key={t.id} className="border-b last:border-0">
                <td className="px-3 py-3 font-medium">{t.document_number}</td>
                <td className="px-3 py-3">{branchName(t.from_branch_id)}</td>
                <td className="px-3 py-3">{branchName(t.to_branch_id)}</td>
                <td className="px-3 py-3 tabular-nums">
                  {t.lines?.reduce((s, l) => s + l.quantity, 0) ?? 0} units
                </td>
                <td className="px-3 py-3 text-muted-foreground">
                  {new Date(t.created_at).toLocaleString("en-PH")}
                </td>
              </tr>
            ))}
            {!items.length ? (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-muted-foreground">
                  No transfers yet.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Transfer stock</DialogTitle>
          </DialogHeader>
          <form onSubmit={onSubmit} className="space-y-3">
            <div className="space-y-2">
              <Label>From branch</Label>
              <SearchableCombobox
                value={form.from_branch_id}
                onValueChange={(v) => setForm({ ...form, from_branch_id: v })}
                options={branches
                  .filter((b) => b.is_active)
                  .map((b) => ({
                    value: b.id,
                    label: `${b.name} (${b.code})`,
                  }))}
              />
            </div>
            <div className="space-y-2">
              <Label>To branch</Label>
              <SearchableCombobox
                value={form.to_branch_id}
                onValueChange={(v) => setForm({ ...form, to_branch_id: v })}
                options={branches
                  .filter((b) => b.is_active)
                  .map((b) => ({
                    value: b.id,
                    label: `${b.name} (${b.code})`,
                  }))}
              />
            </div>
            <div className="space-y-2">
              <Label>Product</Label>
              <SearchableCombobox
                value={form.product_id}
                onValueChange={(v) => setForm({ ...form, product_id: v })}
                options={products.map((p) => ({
                  value: p.id,
                  label: p.name,
                  description: `${p.barcode} · stock ${p.stock_qty}`,
                }))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="qty">Quantity</Label>
              <Input
                id="qty"
                className="min-h-11"
                type="number"
                min={1}
                required
                value={form.quantity}
                onChange={(e) => setForm({ ...form, quantity: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="notes">Notes (optional)</Label>
              <Input
                id="notes"
                className="min-h-11"
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
              />
            </div>
            <Button type="submit" className="min-h-11 w-full" disabled={busy}>
              {busy ? "Transferring…" : "Transfer"}
            </Button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
