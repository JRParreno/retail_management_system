"use client";

import { FormEvent, Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { clientApi, toastError } from "@/lib/client-api";
import type {
  Paginated,
  RefundableSnapshot,
  ReturnVoid,
  Transaction,
} from "@/lib/types";
import { formatPeso } from "@/lib/types";

function RefundsInner() {
  const search = useSearchParams();
  const presetTx = search.get("tx");

  const [q, setQ] = useState("");
  const [results, setResults] = useState<Transaction[]>([]);
  const [snapshot, setSnapshot] = useState<RefundableSnapshot | null>(null);
  const [history, setHistory] = useState<ReturnVoid[]>([]);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [partQty, setPartQty] = useState<Record<string, number>>({});
  const [partRestock, setPartRestock] = useState<Record<string, boolean>>({});
  const [partSelected, setPartSelected] = useState<Record<string, boolean>>({});
  const [laborSelected, setLaborSelected] = useState<Record<string, boolean>>({});

  const loadHistory = useCallback(async () => {
    try {
      setHistory(await clientApi<ReturnVoid[]>("/return-voids?limit=30"));
    } catch (err) {
      toastError(err);
    }
  }, []);

  async function loadSnapshot(transactionId: string) {
    try {
      const data = await clientApi<RefundableSnapshot>(
        `/return-voids/refundable/${transactionId}`,
      );
      setSnapshot(data);
      const qty: Record<string, number> = {};
      const restock: Record<string, boolean> = {};
      const selected: Record<string, boolean> = {};
      for (const p of data.part_lines) {
        qty[p.part_line_id] = p.remaining_qty;
        restock[p.part_line_id] = true;
        selected[p.part_line_id] = p.remaining_qty > 0;
      }
      setPartQty(qty);
      setPartRestock(restock);
      setPartSelected(selected);
      const laborSel: Record<string, boolean> = {};
      for (const l of data.labor_lines) {
        laborSel[l.labor_line_id] = !l.already_refunded;
      }
      setLaborSelected(laborSel);
      setReason("");
    } catch (err) {
      toastError(err);
      setSnapshot(null);
    }
  }

  useEffect(() => {
    loadHistory();
    if (presetTx) {
      void loadSnapshot(presetTx);
    }
  }, [loadHistory, presetTx]);

  async function searchPaid(e?: FormEvent) {
    e?.preventDefault();
    try {
      const params = new URLSearchParams({
        status: "PAID",
        page_size: "20",
      });
      if (q.trim()) params.set("q", q.trim());
      const res = await clientApi<Paginated<Transaction>>(
        `/transactions?${params}`,
      );
      setResults(res.items);
      if (res.items.length === 1) {
        await loadSnapshot(res.items[0].id);
      }
    } catch (err) {
      toastError(err);
    }
  }

  function selectAllRemaining() {
    if (!snapshot) return;
    const selected: Record<string, boolean> = {};
    const qty: Record<string, number> = { ...partQty };
    for (const p of snapshot.part_lines) {
      selected[p.part_line_id] = p.remaining_qty > 0;
      qty[p.part_line_id] = p.remaining_qty;
    }
    setPartSelected(selected);
    setPartQty(qty);
    const laborSel: Record<string, boolean> = {};
    for (const l of snapshot.labor_lines) {
      laborSel[l.labor_line_id] = !l.already_refunded;
    }
    setLaborSelected(laborSel);
  }

  const refundTotal = useMemo(() => {
    if (!snapshot) return 0;
    let total = 0;
    for (const p of snapshot.part_lines) {
      if (!partSelected[p.part_line_id] || p.remaining_qty <= 0) continue;
      const qty = Math.min(
        Math.max(1, partQty[p.part_line_id] ?? 0),
        p.remaining_qty,
      );
      total += Number(p.unit_price) * qty;
    }
    for (const l of snapshot.labor_lines) {
      if (!laborSelected[l.labor_line_id] || l.already_refunded) continue;
      total += Number(l.actual_price);
    }
    return total;
  }, [snapshot, partSelected, partQty, laborSelected]);

  async function submitRefund() {
    if (!snapshot) return;
    if (!reason.trim()) {
      toast.error("Enter a refund reason");
      return;
    }

    const part_lines = snapshot.part_lines
      .filter((p) => partSelected[p.part_line_id] && p.remaining_qty > 0)
      .map((p) => ({
        original_part_line_id: p.part_line_id,
        product_id: p.product_id,
        quantity: Math.min(
          Math.max(1, partQty[p.part_line_id] ?? 1),
          p.remaining_qty,
        ),
        restock: partRestock[p.part_line_id] ?? true,
        unit_refund_amount: p.unit_price,
        cost_price_snapshot: p.cost_price,
      }));

    const labor_lines = snapshot.labor_lines
      .filter((l) => laborSelected[l.labor_line_id] && !l.already_refunded)
      .map((l) => ({
        original_labor_line_id: l.labor_line_id,
        mechanic_id: l.mechanic_id,
        refund_amount: l.actual_price,
        commission_reversal_amount: l.mechanic_payout_amount,
      }));

    if (!part_lines.length && !labor_lines.length) {
      toast.error("Select at least one line to refund");
      return;
    }

    setBusy(true);
    try {
      const rv = await clientApi<ReturnVoid>("/return-voids", {
        method: "POST",
        body: JSON.stringify({
          original_transaction_id: snapshot.transaction_id,
          return_type: "PARTIAL_RETURN",
          reason: reason.trim(),
          part_lines,
          labor_lines,
        }),
      });
      toast.success(`Refund posted: ${rv.document_number}`);
      await loadSnapshot(snapshot.transaction_id);
      await loadHistory();
    } catch (err) {
      toastError(err);
    } finally {
      setBusy(false);
    }
  }

  function refundAmount(rv: ReturnVoid) {
    const parts = rv.part_lines.reduce(
      (s, p) => s + Number(p.unit_refund_amount) * p.quantity,
      0,
    );
    const labor = rv.labor_lines.reduce(
      (s, l) => s + Number(l.refund_amount),
      0,
    );
    return parts + labor;
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Refunds</h1>
        <p className="text-sm text-muted-foreground">
          Refund PAID sales — restock parts and reverse mechanic commission
        </p>
      </div>

      <form
        onSubmit={searchPaid}
        className="no-print flex flex-col gap-2 sm:flex-row"
      >
        <Input
          className="min-h-11"
          placeholder="Search JO# / INV# / plate / customer"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <Button type="submit" className="min-h-11">
          Find paid tickets
        </Button>
      </form>

      {results.length > 0 ? (
        <div className="overflow-x-auto rounded-xl border bg-card">
          <table className="w-full min-w-[560px] text-left text-sm">
            <thead className="border-b bg-muted/40">
              <tr>
                <th className="px-3 py-3">Document</th>
                <th className="px-3 py-3">Customer / plate</th>
                <th className="px-3 py-3">Paid</th>
                <th className="px-3 py-3" />
              </tr>
            </thead>
            <tbody>
              {results.map((tx) => (
                <tr key={tx.id} className="border-b last:border-0">
                  <td className="px-3 py-3 font-medium">{tx.document_number}</td>
                  <td className="px-3 py-3">
                    {tx.customer_name ?? "—"}
                    {tx.plate_number ? ` · ${tx.plate_number}` : ""}
                  </td>
                  <td className="px-3 py-3 text-muted-foreground">
                    {tx.paid_at
                      ? new Date(tx.paid_at).toLocaleString("en-PH")
                      : "—"}
                  </td>
                  <td className="px-3 py-3 text-right">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => loadSnapshot(tx.id)}
                    >
                      Refund
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {snapshot ? (
        <section className="space-y-4 rounded-xl border bg-card p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="text-lg font-semibold">{snapshot.document_number}</p>
              <p className="text-sm text-muted-foreground">
                Select lines to refund
              </p>
            </div>
            <Button variant="secondary" className="min-h-10" onClick={selectAllRemaining}>
              Select all remaining
            </Button>
          </div>

          <div className="space-y-2">
            <h2 className="font-medium">Parts</h2>
            {!snapshot.part_lines.length ? (
              <p className="text-sm text-muted-foreground">No parts on this ticket.</p>
            ) : (
              snapshot.part_lines.map((p) => (
                <label
                  key={p.part_line_id}
                  className="flex flex-col gap-2 rounded-lg border p-3 sm:flex-row sm:items-center"
                >
                  <div className="flex min-w-0 flex-1 items-start gap-2">
                    <input
                      type="checkbox"
                      className="mt-1"
                      disabled={p.remaining_qty <= 0}
                      checked={Boolean(partSelected[p.part_line_id])}
                      onChange={(e) =>
                        setPartSelected({
                          ...partSelected,
                          [p.part_line_id]: e.target.checked,
                        })
                      }
                    />
                    <div className="min-w-0">
                      <p className="font-medium">{p.product_name}</p>
                      <p className="text-xs text-muted-foreground">
                        {p.barcode} · sold {p.original_qty} · returned{" "}
                        {p.returned_qty} · left {p.remaining_qty} ·{" "}
                        {formatPeso(p.unit_price)} each
                      </p>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-3">
                    <Input
                      className="h-9 w-20"
                      type="number"
                      min={1}
                      max={p.remaining_qty}
                      disabled={p.remaining_qty <= 0 || !partSelected[p.part_line_id]}
                      value={partQty[p.part_line_id] ?? 0}
                      onChange={(e) =>
                        setPartQty({
                          ...partQty,
                          [p.part_line_id]: Number(e.target.value),
                        })
                      }
                    />
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        disabled={!partSelected[p.part_line_id]}
                        checked={partRestock[p.part_line_id] ?? true}
                        onChange={(e) =>
                          setPartRestock({
                            ...partRestock,
                            [p.part_line_id]: e.target.checked,
                          })
                        }
                      />
                      Restock
                    </label>
                  </div>
                </label>
              ))
            )}
          </div>

          <div className="space-y-2">
            <h2 className="font-medium">Labor</h2>
            {!snapshot.labor_lines.length ? (
              <p className="text-sm text-muted-foreground">No labor on this ticket.</p>
            ) : (
              snapshot.labor_lines.map((l) => (
                <label
                  key={l.labor_line_id}
                  className="flex items-start gap-2 rounded-lg border p-3"
                >
                  <input
                    type="checkbox"
                    className="mt-1"
                    disabled={l.already_refunded}
                    checked={Boolean(laborSelected[l.labor_line_id])}
                    onChange={(e) =>
                      setLaborSelected({
                        ...laborSelected,
                        [l.labor_line_id]: e.target.checked,
                      })
                    }
                  />
                  <div>
                    <p className="font-medium">{l.service_name}</p>
                    <p className="text-xs text-muted-foreground">
                      {formatPeso(l.actual_price)}
                      {l.already_refunded ? " · already refunded" : ""}
                      {Number(l.mechanic_payout_amount) > 0
                        ? ` · commission reverse ${formatPeso(l.mechanic_payout_amount)}`
                        : ""}
                    </p>
                  </div>
                </label>
              ))
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="reason">Reason</Label>
            <Textarea
              id="reason"
              required
              placeholder="Customer returned part / wrong item / etc."
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </div>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-lg font-semibold tabular-nums">
              Refund total {formatPeso(refundTotal)}
            </p>
            <Button
              className="min-h-11"
              disabled={busy || refundTotal <= 0}
              onClick={submitRefund}
            >
              {busy ? "Posting…" : "Post refund"}
            </Button>
          </div>
        </section>
      ) : null}

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Recent refunds</h2>
        <div className="overflow-x-auto rounded-xl border bg-card">
          <table className="w-full min-w-[560px] text-left text-sm">
            <thead className="border-b bg-muted/40">
              <tr>
                <th className="px-3 py-3">RV#</th>
                <th className="px-3 py-3">Type</th>
                <th className="px-3 py-3">Amount</th>
                <th className="px-3 py-3">Reason</th>
                <th className="px-3 py-3">When</th>
              </tr>
            </thead>
            <tbody>
              {history.map((rv) => (
                <tr key={rv.id} className="border-b last:border-0">
                  <td className="px-3 py-3 font-medium">{rv.document_number}</td>
                  <td className="px-3 py-3">
                    <Badge variant="secondary">{rv.return_type}</Badge>
                  </td>
                  <td className="px-3 py-3 tabular-nums">
                    {formatPeso(refundAmount(rv))}
                  </td>
                  <td className="px-3 py-3 text-muted-foreground">{rv.reason}</td>
                  <td className="px-3 py-3 text-muted-foreground">
                    {new Date(rv.created_at).toLocaleString("en-PH")}
                  </td>
                </tr>
              ))}
              {!history.length ? (
                <tr>
                  <td colSpan={5} className="px-3 py-6 text-muted-foreground">
                    No refunds yet for this branch.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

export default function RefundsPage() {
  return (
    <Suspense fallback={<p className="text-sm text-muted-foreground">Loading…</p>}>
      <RefundsInner />
    </Suspense>
  );
}
