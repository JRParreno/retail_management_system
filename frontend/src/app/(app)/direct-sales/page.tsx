"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { FileDown, RefreshCw, ShoppingCart } from "lucide-react";

import { useBranch } from "@/components/branch/branch-context";
import { useShop } from "@/components/shop/shop-context";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { clientApi, toastError } from "@/lib/client-api";
import type { Paginated, ReportSummary, Transaction } from "@/lib/types";
import { formatPeso } from "@/lib/types";
import { cn } from "@/lib/utils";

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function formatRangeLabel(start: string, end: string) {
  const opts: Intl.DateTimeFormatOptions = {
    year: "numeric",
    month: "short",
    day: "numeric",
  };
  const s = new Date(`${start}T00:00:00`).toLocaleDateString("en-PH", opts);
  const e = new Date(`${end}T00:00:00`).toLocaleDateString("en-PH", opts);
  return s === e ? s : `${s} – ${e}`;
}

function fileSafeName(name: string) {
  return (
    name
      .trim()
      .replace(/[^a-zA-Z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "") || "Shop"
  );
}

function formatPaidAt(value: string | null | undefined) {
  if (!value) return "—";
  return new Date(value).toLocaleString("en-PH", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function isInRange(value: string | null | undefined, start: string, end: string) {
  if (!value) return false;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return false;
  const local = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  return local >= start && local <= end;
}

export default function DirectSalesPage() {
  const { activeBranch, user } = useBranch();
  const { settings } = useShop();
  const isAdmin = user?.role === "ADMIN";
  const [start, setStart] = useState(todayISO());
  const [end, setEnd] = useState(todayISO());
  const [summary, setSummary] = useState<ReportSummary | null>(null);
  const [sales, setSales] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");

  const load = useCallback(
    async (s = start, e = end) => {
      setLoading(true);
      try {
        const [report, list] = await Promise.all([
          clientApi<ReportSummary>(
            `/reports/summary?start_date=${s}&end_date=${e}&transaction_type=DIRECT_SALE`,
          ),
          clientApi<Paginated<Transaction>>(
            "/transactions?transaction_type=DIRECT_SALE&status=PAID&page_size=100",
          ),
        ]);
        setSummary(report);
        setSales(
          list.items
            .filter((sale) => isInRange(sale.paid_at ?? sale.created_at, s, e))
            .sort((a, b) => {
              const ax = a.paid_at ?? a.created_at;
              const bx = b.paid_at ?? b.created_at;
              return bx.localeCompare(ax);
            }),
        );
      } catch (err) {
        toastError(err);
      } finally {
        setLoading(false);
      }
    },
    [start, end],
  );

  useEffect(() => {
    void load();
  }, [load]);

  function preset(days: number) {
    const endDate = new Date();
    const startDate = new Date();
    startDate.setDate(endDate.getDate() - days + 1);
    const s = startDate.toISOString().slice(0, 10);
    const e = endDate.toISOString().slice(0, 10);
    setStart(s);
    setEnd(e);
    void load(s, e);
  }

  function exportPdf() {
    if (!summary) return;
    const previous = document.title;
    document.title = `${fileSafeName(settings.business_name)}-DirectSales-${start}_to_${end}`;
    window.print();
    document.title = previous;
  }

  const filteredProducts = useMemo(() => {
    const rows = summary?.product_sales ?? [];
    const term = q.trim().toLowerCase();
    if (!term) return rows;
    return rows.filter(
      (row) =>
        row.product_name.toLowerCase().includes(term) ||
        row.barcode.toLowerCase().includes(term) ||
        (row.brand?.toLowerCase().includes(term) ?? false),
    );
  }, [summary, q]);

  const totalQty = useMemo(
    () => filteredProducts.reduce((sum, row) => sum + row.quantity_sold, 0),
    [filteredProducts],
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Direct sales
          </h1>
          <p className="text-sm text-muted-foreground">
            Counter purchases only for {activeBranch?.name ?? "active branch"} —
            products and tickets
          </p>
        </div>
        <div className="no-print flex flex-wrap gap-2">
          <Link
            href="/pos"
            className={cn(buttonVariants(), "min-h-11 gap-2")}
          >
            <ShoppingCart className="size-4" />
            New sale
          </Link>
          <Button
            className="min-h-11 gap-2"
            variant="outline"
            disabled={!summary || loading}
            onClick={exportPdf}
          >
            <FileDown className="size-4" />
            Export PDF
          </Button>
        </div>
      </div>

      <div className="no-print flex flex-wrap gap-2">
        <Button variant="secondary" className="min-h-11" onClick={() => preset(1)}>
          Today
        </Button>
        <Button variant="secondary" className="min-h-11" onClick={() => preset(7)}>
          Week
        </Button>
        <Button variant="secondary" className="min-h-11" onClick={() => preset(30)}>
          Month
        </Button>
        <Button
          variant="outline"
          className="min-h-11 gap-2"
          disabled={loading}
          onClick={() => load()}
        >
          <RefreshCw className={cn("size-4", loading && "animate-spin")} />
          Refresh
        </Button>
      </div>

      <div className="no-print flex flex-col gap-2 sm:flex-row sm:items-end">
        <div className="space-y-2">
          <Label>Start</Label>
          <Input
            type="date"
            className="min-h-11"
            value={start}
            onChange={(e) => setStart(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label>End</Label>
          <Input
            type="date"
            className="min-h-11"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
          />
        </div>
        <Button className="min-h-11" onClick={() => load()} disabled={loading}>
          Apply
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <div className="rounded-xl border bg-card px-3 py-3">
          <p className="text-xs text-muted-foreground">Tickets</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums">
            {loading || !summary ? "—" : summary.transaction_count}
          </p>
        </div>
        <div className="rounded-xl border bg-card px-3 py-3">
          <p className="text-xs text-muted-foreground">Products sold</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums">
            {loading || !summary
              ? "—"
              : summary.product_sales.reduce(
                  (sum, row) => sum + row.quantity_sold,
                  0,
                )}
          </p>
        </div>
        <div className="rounded-xl border bg-card px-3 py-3">
          <p className="text-xs text-muted-foreground">Sales total</p>
          <p className="mt-1 text-xl font-semibold tabular-nums sm:text-2xl">
            {loading || !summary ? "—" : formatPeso(summary.parts_sales)}
          </p>
        </div>
        {isAdmin ? (
          <div className="rounded-xl border bg-card px-3 py-3">
            <p className="text-xs text-muted-foreground">Parts profit</p>
            <p className="mt-1 text-xl font-semibold tabular-nums sm:text-2xl">
              {loading || !summary ? "—" : formatPeso(summary.parts_profit)}
            </p>
          </div>
        ) : (
          <div className="rounded-xl border bg-card px-3 py-3">
            <p className="text-xs text-muted-foreground">SKUs</p>
            <p className="mt-1 text-2xl font-semibold tabular-nums">
              {loading || !summary ? "—" : summary.product_sales.length}
            </p>
          </div>
        )}
      </div>

      <div className="report-screen-only space-y-4">
        <section className="space-y-3">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold">Products purchased</h2>
              <p className="text-sm text-muted-foreground">
                All items sold through direct sale in this period
              </p>
            </div>
            <Input
              className="no-print min-h-11 sm:max-w-xs"
              placeholder="Search product, brand, barcode"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>

          {loading ? (
            <p className="rounded-xl border bg-card px-4 py-6 text-sm text-muted-foreground">
              Loading products…
            </p>
          ) : filteredProducts.length ? (
            <div className="overflow-x-auto rounded-xl border bg-card">
              <table className="w-full min-w-[720px] text-left text-sm">
                <thead className="border-b bg-muted/40">
                  <tr>
                    <th className="px-3 py-3">Product</th>
                    <th className="px-3 py-3">Barcode</th>
                    <th className="px-3 py-3 text-right">Qty</th>
                    <th className="px-3 py-3 text-right">Sales</th>
                    {isAdmin ? (
                      <>
                        <th className="px-3 py-3 text-right">COGS</th>
                        <th className="px-3 py-3 text-right">Profit</th>
                      </>
                    ) : null}
                  </tr>
                </thead>
                <tbody>
                  {filteredProducts.map((row) => (
                    <tr key={row.product_id} className="border-b last:border-0">
                      <td className="px-3 py-3">
                        <p className="font-medium">{row.product_name}</p>
                        {row.brand ? (
                          <p className="text-xs text-muted-foreground">
                            {row.brand}
                          </p>
                        ) : null}
                      </td>
                      <td className="px-3 py-3 font-mono text-xs text-muted-foreground">
                        {row.barcode}
                      </td>
                      <td className="px-3 py-3 text-right tabular-nums font-medium">
                        {row.quantity_sold}
                      </td>
                      <td className="px-3 py-3 text-right tabular-nums">
                        {formatPeso(row.sales_total)}
                      </td>
                      {isAdmin ? (
                        <>
                          <td className="px-3 py-3 text-right tabular-nums">
                            {formatPeso(row.cogs_total)}
                          </td>
                          <td className="px-3 py-3 text-right tabular-nums font-medium">
                            {formatPeso(row.profit)}
                          </td>
                        </>
                      ) : null}
                    </tr>
                  ))}
                </tbody>
                <tfoot className="border-t bg-muted/30 font-medium">
                  <tr>
                    <td className="px-3 py-3" colSpan={2}>
                      Shown ({filteredProducts.length} SKU
                      {filteredProducts.length === 1 ? "" : "s"})
                    </td>
                    <td className="px-3 py-3 text-right tabular-nums">
                      {totalQty}
                    </td>
                    <td className="px-3 py-3 text-right tabular-nums">
                      {formatPeso(
                        filteredProducts.reduce(
                          (sum, row) => sum + Number(row.sales_total),
                          0,
                        ),
                      )}
                    </td>
                    {isAdmin ? (
                      <>
                        <td className="px-3 py-3 text-right tabular-nums">
                          {formatPeso(
                            filteredProducts.reduce(
                              (sum, row) => sum + Number(row.cogs_total),
                              0,
                            ),
                          )}
                        </td>
                        <td className="px-3 py-3 text-right tabular-nums">
                          {formatPeso(
                            filteredProducts.reduce(
                              (sum, row) => sum + Number(row.profit),
                              0,
                            ),
                          )}
                        </td>
                      </>
                    ) : null}
                  </tr>
                </tfoot>
              </table>
            </div>
          ) : (
            <p className="rounded-xl border bg-card px-4 py-6 text-sm text-muted-foreground">
              No direct-sale products in this period.{" "}
              <Link href="/pos" className="font-medium text-primary underline">
                Open counter checkout
              </Link>
            </p>
          )}
        </section>

        <section className="rounded-xl border bg-card">
          <div className="border-b px-4 py-3">
            <h2 className="font-semibold">Tickets</h2>
            <p className="text-xs text-muted-foreground">
              Each completed counter invoice — tap to view the products on that
              sale
            </p>
          </div>
          <ul className="divide-y">
            {sales.map((sale) => {
              const itemCount = sale.part_lines.reduce(
                (sum, line) => sum + line.quantity,
                0,
              );
              return (
                <li key={sale.id}>
                  <Link
                    href={`/jobs/${sale.id}`}
                    className="flex items-start justify-between gap-3 px-4 py-3 transition-colors hover:bg-muted/40"
                  >
                    <span className="min-w-0">
                      <span className="block truncate font-semibold">
                        {sale.document_number}
                      </span>
                      <span className="block truncate text-sm text-muted-foreground">
                        {itemCount} item{itemCount === 1 ? "" : "s"}
                        {sale.customer_name ? ` · ${sale.customer_name}` : ""}
                      </span>
                      <span className="mt-1 block text-xs text-muted-foreground">
                        {formatPaidAt(sale.paid_at ?? sale.created_at)}
                      </span>
                    </span>
                    <span className="shrink-0 text-right">
                      <span className="block tabular-nums font-semibold">
                        {formatPeso(sale.totals?.net_total ?? 0)}
                      </span>
                      <Badge variant="outline" className="mt-1">
                        Paid
                      </Badge>
                    </span>
                  </Link>
                </li>
              );
            })}
            {!loading && !sales.length ? (
              <li className="px-4 py-8 text-sm text-muted-foreground">
                No direct sale tickets in this period.
              </li>
            ) : null}
            {loading ? (
              <li className="px-4 py-8 text-sm text-muted-foreground">
                Loading tickets…
              </li>
            ) : null}
          </ul>
        </section>
      </div>

      <div className="report-print-area report-print-only">
        <h1>{settings.business_name} — Direct Sales Report</h1>
        <p className="report-print-meta">
          Branch: {activeBranch?.name ?? "—"} ({activeBranch?.code ?? "—"})
          <br />
          Period: {formatRangeLabel(start, end)}
          <br />
          Generated: {new Date().toLocaleString("en-PH")}
        </p>
        <h2 style={{ fontSize: "13pt", margin: "14pt 0 6pt" }}>Overview</h2>
        <table className="report-print-table">
          <tbody>
            <tr>
              <td>Tickets</td>
              <td>{summary?.transaction_count ?? 0}</td>
            </tr>
            <tr>
              <td>Sales total</td>
              <td>{formatPeso(summary?.parts_sales ?? 0)}</td>
            </tr>
            {isAdmin ? (
              <tr>
                <td>Parts profit</td>
                <td>{formatPeso(summary?.parts_profit ?? 0)}</td>
              </tr>
            ) : null}
          </tbody>
        </table>
        <h2 style={{ fontSize: "13pt", margin: "14pt 0 6pt" }}>
          Products purchased
        </h2>
        {summary?.product_sales?.length ? (
          <table className="report-print-table">
            <thead>
              <tr>
                <th>Product</th>
                <th>Barcode</th>
                <th>Qty</th>
                <th>Sales</th>
                {isAdmin ? (
                  <>
                    <th>COGS</th>
                    <th>Profit</th>
                  </>
                ) : null}
              </tr>
            </thead>
            <tbody>
              {summary.product_sales.map((row) => (
                <tr key={row.product_id}>
                  <td>
                    {row.product_name}
                    {row.brand ? ` (${row.brand})` : ""}
                  </td>
                  <td>{row.barcode}</td>
                  <td>{row.quantity_sold}</td>
                  <td>{formatPeso(row.sales_total)}</td>
                  {isAdmin ? (
                    <>
                      <td>{formatPeso(row.cogs_total)}</td>
                      <td>{formatPeso(row.profit)}</td>
                    </>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p>No direct-sale products in this period.</p>
        )}
      </div>
    </div>
  );
}
