"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { FileDown } from "lucide-react";

import { useBranch } from "@/components/branch/branch-context";
import { useShop } from "@/components/shop/shop-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { clientApi, toastError } from "@/lib/client-api";
import type { ReportSummary } from "@/lib/types";
import { formatPeso } from "@/lib/types";

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

export default function ReportsPage() {
  const router = useRouter();
  const { activeBranch, user } = useBranch();
  const { settings } = useShop();
  const isAdmin = user?.role === "ADMIN";
  const [start, setStart] = useState(todayISO());
  const [end, setEnd] = useState(todayISO());
  const [summary, setSummary] = useState<ReportSummary | null>(null);

  useEffect(() => {
    if (user && user.role !== "ADMIN") {
      router.replace("/dashboard");
    }
  }, [user, router]);

  async function load(s = start, e = end) {
    try {
      const data = await clientApi<ReportSummary>(
        `/reports/summary?start_date=${s}&end_date=${e}`,
      );
      setSummary(data);
    } catch (err) {
      toastError(err);
    }
  }

  useEffect(() => {
    if (!isAdmin) return;
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAdmin]);

  if (user && !isAdmin) {
    return null;
  }

  function preset(days: number) {
    const endDate = new Date();
    const startDate = new Date();
    startDate.setDate(endDate.getDate() - days + 1);
    const s = startDate.toISOString().slice(0, 10);
    const e = endDate.toISOString().slice(0, 10);
    setStart(s);
    setEnd(e);
    load(s, e);
  }

  function exportPdf() {
    if (!summary) return;
    const previous = document.title;
    document.title = `${fileSafeName(settings.business_name)}-Report-${start}_to_${end}`;
    window.print();
    document.title = previous;
  }

  const profitRows =
    summary && isAdmin
      ? ([
          ["Parts profit", formatPeso(summary.parts_profit)],
          [
            "Labor (before commission)",
            formatPeso(summary.labor_profit_before_commission),
          ],
          ["Gross profit", formatPeso(summary.gross_profit)],
          [
            "Commission gross",
            formatPeso(summary.commission_gross_total ?? summary.commission_total),
          ],
          [
            "Commission waived",
            formatPeso(summary.commission_waived_total ?? 0),
          ],
          ["Commission net", formatPeso(summary.commission_total)],
          ["Net profit", formatPeso(summary.net_profit)],
        ] as const)
      : [];

  const opsRows = summary
    ? ([
        ["Gross revenue", formatPeso(summary.gross_revenue)],
        ...(isAdmin
          ? ([["COGS", formatPeso(summary.cogs)]] as const)
          : []),
        ["Parts sales", formatPeso(summary.parts_sales)],
        ["Labor sales", formatPeso(summary.labor_sales)],
        ["Avg ticket", formatPeso(summary.avg_ticket)],
        ["Tickets", String(summary.transaction_count)],
        ["Low stock SKUs", String(summary.low_stock_count)],
      ] as const)
    : [];

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Reports</h1>
          <p className="text-sm text-muted-foreground">
            {isAdmin ? "Profit & sales" : "Sales"} for{" "}
            {activeBranch?.name ?? "active branch"} — export PDF anytime
          </p>
        </div>
        <Button
          className="no-print min-h-11 gap-2"
          variant="outline"
          disabled={!summary}
          onClick={exportPdf}
        >
          <FileDown className="size-4" />
          Export PDF
        </Button>
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
        <Button className="min-h-11" onClick={() => load()}>
          Apply
        </Button>
      </div>

      {summary ? (
        <>
          <div className="report-screen-only space-y-4">
            {isAdmin && profitRows.length ? (
              <div>
                <h2 className="mb-2 text-lg font-semibold">Profit</h2>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {profitRows.map(([label, value]) => (
                    <div key={label} className="rounded-xl border bg-card p-4">
                      <p className="text-sm text-muted-foreground">{label}</p>
                      <p className="mt-1 text-2xl font-semibold tabular-nums">
                        {value}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            <div>
              <h2 className="mb-2 text-lg font-semibold">Sales overview</h2>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {opsRows.map(([label, value]) => (
                  <div key={label} className="rounded-xl border bg-card p-4">
                    <p className="text-sm text-muted-foreground">{label}</p>
                    <p className="mt-1 text-2xl font-semibold tabular-nums">
                      {value}
                    </p>
                  </div>
                ))}
              </div>
            </div>

            {summary.mechanic_commissions?.length ? (
              <div>
                <h2 className="mb-2 text-lg font-semibold">
                  Commission computation by mechanic
                </h2>
                <div className="overflow-x-auto rounded-xl border bg-card">
                  <table className="w-full min-w-[640px] text-left text-sm">
                    <thead className="border-b bg-muted/40">
                      <tr>
                        <th className="px-3 py-3">Mechanic</th>
                        <th className="px-3 py-3">Labor sales</th>
                        <th className="px-3 py-3">Gross</th>
                        <th className="px-3 py-3">Waived</th>
                        <th className="px-3 py-3">Net payout</th>
                      </tr>
                    </thead>
                    <tbody>
                      {summary.mechanic_commissions.map((row) => (
                        <tr key={row.mechanic_id} className="border-b last:border-0">
                          <td className="px-3 py-3 font-medium">
                            {row.nickname}
                            {row.is_first_mechanic_waived ? (
                              <span className="ml-2 text-xs text-muted-foreground">
                                (first / waived)
                              </span>
                            ) : null}
                          </td>
                          <td className="px-3 py-3 tabular-nums">
                            {formatPeso(row.labor_sales)}
                          </td>
                          <td className="px-3 py-3 tabular-nums">
                            {formatPeso(row.commission_gross ?? row.commission_total)}
                          </td>
                          <td className="px-3 py-3 tabular-nums">
                            {formatPeso(row.commission_waived ?? 0)}
                          </td>
                          <td className="px-3 py-3 tabular-nums font-medium">
                            {formatPeso(row.commission_total)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : null}

            <div>
              <h2 className="mb-2 text-lg font-semibold">Product sales</h2>
              <p className="mb-2 text-sm text-muted-foreground">
                All parts sold in this period (direct sales + service jobs)
              </p>
              {summary.product_sales?.length ? (
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
                      {summary.product_sales.map((row) => (
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
                          Total ({summary.product_sales.length} SKU
                          {summary.product_sales.length === 1 ? "" : "s"})
                        </td>
                        <td className="px-3 py-3 text-right tabular-nums">
                          {summary.product_sales.reduce(
                            (sum, row) => sum + row.quantity_sold,
                            0,
                          )}
                        </td>
                        <td className="px-3 py-3 text-right tabular-nums">
                          {formatPeso(summary.parts_sales)}
                        </td>
                        {isAdmin ? (
                          <>
                            <td className="px-3 py-3 text-right tabular-nums">
                              {formatPeso(summary.cogs)}
                            </td>
                            <td className="px-3 py-3 text-right tabular-nums">
                              {formatPeso(summary.parts_profit)}
                            </td>
                          </>
                        ) : null}
                      </tr>
                    </tfoot>
                  </table>
                </div>
              ) : (
                <p className="rounded-xl border bg-card px-4 py-6 text-sm text-muted-foreground">
                  No product sales in this period.
                </p>
              )}
            </div>
          </div>

          <div className="report-print-area report-print-only">
            <h1>
              {settings.business_name} —{" "}
              {isAdmin ? "Profit & Sales Report" : "Sales Report"}
            </h1>
            <p className="report-print-meta">
              Branch: {activeBranch?.name ?? "—"} ({activeBranch?.code ?? "—"})
              <br />
              Period: {formatRangeLabel(start, end)}
              <br />
              Generated: {new Date().toLocaleString("en-PH")}
            </p>
            {isAdmin && profitRows.length ? (
              <>
                <h2 style={{ fontSize: "13pt", marginBottom: "6pt" }}>
                  Profit
                </h2>
                <table className="report-print-table">
                  <thead>
                    <tr>
                      <th>Metric</th>
                      <th>Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {profitRows.map(([label, value]) => (
                      <tr key={label}>
                        <td>{label}</td>
                        <td>{value}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            ) : null}
            <h2 style={{ fontSize: "13pt", margin: "14pt 0 6pt" }}>
              Sales overview
            </h2>
            <table className="report-print-table">
              <thead>
                <tr>
                  <th>Metric</th>
                  <th>Amount</th>
                </tr>
              </thead>
              <tbody>
                {opsRows.map(([label, value]) => (
                  <tr key={label}>
                    <td>{label}</td>
                    <td>{value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {summary.mechanic_commissions?.length ? (
              <>
                <h2 style={{ fontSize: "13pt", margin: "14pt 0 6pt" }}>
                  Commission computation by mechanic
                </h2>
                <table className="report-print-table">
                  <thead>
                    <tr>
                      <th>Mechanic</th>
                      <th>Labor</th>
                      <th>Gross</th>
                      <th>Waived</th>
                      <th>Net</th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.mechanic_commissions.map((row) => (
                      <tr key={row.mechanic_id}>
                        <td>
                          {row.nickname}
                          {row.is_first_mechanic_waived ? " (first/waived)" : ""}
                        </td>
                        <td>{formatPeso(row.labor_sales)}</td>
                        <td>
                          {formatPeso(row.commission_gross ?? row.commission_total)}
                        </td>
                        <td>{formatPeso(row.commission_waived ?? 0)}</td>
                        <td>{formatPeso(row.commission_total)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            ) : null}
            <h2 style={{ fontSize: "13pt", margin: "14pt 0 6pt" }}>
              Product sales
            </h2>
            {summary.product_sales?.length ? (
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
                  <tr>
                    <td colSpan={2}>
                      Total ({summary.product_sales.length} SKUs)
                    </td>
                    <td>
                      {summary.product_sales.reduce(
                        (sum, row) => sum + row.quantity_sold,
                        0,
                      )}
                    </td>
                    <td>{formatPeso(summary.parts_sales)}</td>
                    {isAdmin ? (
                      <>
                        <td>{formatPeso(summary.cogs)}</td>
                        <td>{formatPeso(summary.parts_profit)}</td>
                      </>
                    ) : null}
                  </tr>
                </tbody>
              </table>
            ) : (
              <p>No product sales in this period.</p>
            )}
          </div>
        </>
      ) : null}
    </div>
  );
}
