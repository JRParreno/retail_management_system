"use client";

import { useEffect, useState } from "react";
import { FileDown } from "lucide-react";

import { useBranch } from "@/components/branch/branch-context";
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

export default function ReportsPage() {
  const { activeBranch } = useBranch();
  const [start, setStart] = useState(todayISO());
  const [end, setEnd] = useState(todayISO());
  const [summary, setSummary] = useState<ReportSummary | null>(null);

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
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
    document.title = `MotoShop-Report-${start}_to_${end}`;
    window.print();
    document.title = previous;
  }

  const profitRows = summary
    ? ([
        ["Parts profit", formatPeso(summary.parts_profit)],
        ["Labor (before commission)", formatPeso(summary.labor_profit_before_commission)],
        ["Gross profit", formatPeso(summary.gross_profit)],
        ["Commissions", formatPeso(summary.commission_total)],
        ["Net profit", formatPeso(summary.net_profit)],
      ] as const)
    : [];

  const opsRows = summary
    ? ([
        ["Gross revenue", formatPeso(summary.gross_revenue)],
        ["COGS", formatPeso(summary.cogs)],
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
            Profit for {activeBranch?.name ?? "active branch"} — export PDF anytime
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
                  Commission by mechanic
                </h2>
                <div className="overflow-x-auto rounded-xl border bg-card">
                  <table className="w-full min-w-[480px] text-left text-sm">
                    <thead className="border-b bg-muted/40">
                      <tr>
                        <th className="px-3 py-3">Mechanic</th>
                        <th className="px-3 py-3">Labor sales</th>
                        <th className="px-3 py-3">Commission</th>
                      </tr>
                    </thead>
                    <tbody>
                      {summary.mechanic_commissions.map((row) => (
                        <tr key={row.mechanic_id} className="border-b last:border-0">
                          <td className="px-3 py-3 font-medium">{row.nickname}</td>
                          <td className="px-3 py-3 tabular-nums">
                            {formatPeso(row.labor_sales)}
                          </td>
                          <td className="px-3 py-3 tabular-nums">
                            {formatPeso(row.commission_total)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : null}
          </div>

          <div className="report-print-area report-print-only">
            <h1>MotoShop RMS — Profit & Sales Report</h1>
            <p className="report-print-meta">
              Branch: {activeBranch?.name ?? "—"} ({activeBranch?.code ?? "—"})
              <br />
              Period: {formatRangeLabel(start, end)}
              <br />
              Generated: {new Date().toLocaleString("en-PH")}
            </p>
            <h2 style={{ fontSize: "13pt", marginBottom: "6pt" }}>Profit</h2>
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
                  Commission by mechanic
                </h2>
                <table className="report-print-table">
                  <thead>
                    <tr>
                      <th>Mechanic</th>
                      <th>Labor</th>
                      <th>Commission</th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.mechanic_commissions.map((row) => (
                      <tr key={row.mechanic_id}>
                        <td>{row.nickname}</td>
                        <td>{formatPeso(row.labor_sales)}</td>
                        <td>{formatPeso(row.commission_total)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            ) : null}
          </div>
        </>
      ) : null}
    </div>
  );
}
