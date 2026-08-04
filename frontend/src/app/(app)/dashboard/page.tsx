"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ClipboardList,
  Package,
  Receipt,
  RotateCcw,
  ShoppingCart,
  Wrench,
} from "lucide-react";

import { useBranch } from "@/components/branch/branch-context";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { clientApi, toastError } from "@/lib/client-api";
import type {
  CashierShift,
  Paginated,
  Product,
  ReportSummary,
  Transaction,
  TransactionStatus,
} from "@/lib/types";
import { formatPeso } from "@/lib/types";
import { cn } from "@/lib/utils";

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function statusLabel(status: TransactionStatus) {
  if (status === "DONE") return "Awaiting pay";
  if (status === "IN_PROGRESS") return "In progress";
  return status.charAt(0) + status.slice(1).toLowerCase();
}

function statusBadgeVariant(
  status: TransactionStatus,
): "default" | "secondary" | "outline" | "destructive" {
  if (status === "IN_PROGRESS") return "default";
  if (status === "DONE") return "secondary";
  if (status === "CANCELLED") return "destructive";
  return "outline";
}

function formatStarted(value: string | null | undefined) {
  if (!value) return "—";
  return new Date(value).toLocaleString("en-PH", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

const SHORTCUTS = [
  { href: "/jobs/new", label: "New job", icon: ClipboardList, primary: true },
  { href: "/pos", label: "Direct sale", icon: ShoppingCart },
  { href: "/jobs", label: "Job board", icon: ClipboardList },
  { href: "/inventory", label: "Inventory", icon: Package },
  { href: "/refunds", label: "Refunds", icon: RotateCcw },
  { href: "/mechanics", label: "Mechanics", icon: Wrench },
  { href: "/reports", label: "Full reports", icon: Receipt },
] as const;

export default function DashboardPage() {
  const router = useRouter();
  const { activeBranch } = useBranch();
  const [summary, setSummary] = useState<ReportSummary | null>(null);
  const [activeJobs, setActiveJobs] = useState<Transaction[]>([]);
  const [inProgressCount, setInProgressCount] = useState(0);
  const [awaitingPayCount, setAwaitingPayCount] = useState(0);
  const [lowStockItems, setLowStockItems] = useState<Product[]>([]);
  const [shift, setShift] = useState<CashierShift | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const today = todayISO();
    try {
      const [report, inProgress, awaitingPay, products, currentShift] =
        await Promise.all([
          clientApi<ReportSummary>(
            `/reports/summary?start_date=${today}&end_date=${today}`,
          ),
          clientApi<Paginated<Transaction>>(
            "/transactions?transaction_type=SERVICE_JOB&status=IN_PROGRESS&page_size=50",
          ),
          clientApi<Paginated<Transaction>>(
            "/transactions?transaction_type=SERVICE_JOB&status=DONE&page_size=50",
          ),
          clientApi<Paginated<Product>>("/products?page_size=100"),
          clientApi<CashierShift | null>("/shifts/current").catch(() => null),
        ]);

      setSummary(report);
      setInProgressCount(inProgress.total);
      setAwaitingPayCount(awaitingPay.total);
      setActiveJobs(
        [...inProgress.items, ...awaitingPay.items].sort((a, b) => {
          const ax = a.started_at ?? a.created_at;
          const bx = b.started_at ?? b.created_at;
          return bx.localeCompare(ax);
        }),
      );
      setLowStockItems(
        products.items
          .filter((p) => p.stock_qty <= p.min_stock_threshold)
          .sort((a, b) => a.stock_qty - b.stock_qty)
          .slice(0, 6),
      );
      setShift(currentShift);
    } catch (err) {
      toastError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function openShift() {
    try {
      const s = await clientApi<CashierShift>("/shifts/open", {
        method: "POST",
        body: JSON.stringify({ opening_float: "0.00" }),
      });
      setShift(s);
    } catch (err) {
      toastError(err);
    }
  }

  const queuePreview = useMemo(() => activeJobs.slice(0, 8), [activeJobs]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground">
            {activeBranch?.name ?? "Branch"} floor board — today&apos;s numbers,
            open jobs, and shortcuts
          </p>
        </div>
        <Button
          className="min-h-11"
          variant="outline"
          onClick={load}
          disabled={loading}
        >
          Refresh
        </Button>
      </div>

      <div className="rounded-xl border bg-card p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-medium">Cashier shift</p>
            <p className="text-sm text-muted-foreground">
              {loading
                ? "Loading…"
                : shift?.status === "OPEN"
                  ? `Open since ${new Date(shift.opened_at).toLocaleTimeString("en-PH")}`
                  : "No open shift — open one before taking payments"}
            </p>
          </div>
          {shift?.status !== "OPEN" ? (
            <Button className="min-h-11" onClick={openShift}>
              Open shift
            </Button>
          ) : (
            <Link
              href="/shifts"
              className={cn(buttonVariants({ variant: "outline" }), "min-h-11")}
            >
              Manage shift
            </Link>
          )}
        </div>
      </div>

      <section className="space-y-3">
        <div className="flex items-end justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">Today</h2>
            <p className="text-xs text-muted-foreground">
              Live summary for {todayISO()}
            </p>
          </div>
          <Link
            href="/reports"
            className={cn(
              buttonVariants({ variant: "ghost", size: "sm" }),
              "min-h-9",
            )}
          >
            Open reports
          </Link>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {[
            {
              label: "Gross revenue",
              value: summary ? formatPeso(summary.gross_revenue) : "—",
            },
            {
              label: "Net profit",
              value: summary ? formatPeso(summary.net_profit) : "—",
            },
            {
              label: "Tickets",
              value: summary ? String(summary.transaction_count) : "—",
            },
            {
              label: "Avg ticket",
              value: summary ? formatPeso(summary.avg_ticket) : "—",
            },
          ].map((card) => (
            <Link
              key={card.label}
              href="/reports"
              className="rounded-xl border bg-card p-4 transition-colors hover:border-primary/40"
            >
              <p className="text-sm text-muted-foreground">{card.label}</p>
              <p className="mt-1 text-2xl font-semibold tabular-nums">
                {loading ? "—" : card.value}
              </p>
            </Link>
          ))}
        </div>
        {summary && !loading ? (
          <p className="text-xs text-muted-foreground">
            Parts {formatPeso(summary.parts_sales)} · Labor{" "}
            {formatPeso(summary.labor_sales)} · Commissions{" "}
            {formatPeso(summary.commission_total)}
          </p>
        ) : null}
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Work queue</h2>
        <div className="grid gap-3 sm:grid-cols-3">
          <Link
            href="/jobs?status=IN_PROGRESS"
            className="rounded-xl border bg-card p-4 transition-colors hover:border-primary/40"
          >
            <div className="mb-2 flex items-center justify-between">
              <span className="text-sm text-muted-foreground">In progress</span>
              <ClipboardList className="size-5 text-primary" />
            </div>
            <p className="text-3xl font-semibold tabular-nums">
              {loading ? "—" : inProgressCount}
            </p>
          </Link>
          <Link
            href="/jobs?status=DONE"
            className="rounded-xl border bg-card p-4 transition-colors hover:border-primary/40"
          >
            <div className="mb-2 flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Awaiting pay</span>
              <ShoppingCart className="size-5 text-primary" />
            </div>
            <p className="text-3xl font-semibold tabular-nums">
              {loading ? "—" : awaitingPayCount}
            </p>
          </Link>
          <Link
            href="/inventory"
            className="rounded-xl border bg-card p-4 transition-colors hover:border-primary/40"
          >
            <div className="mb-2 flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Low stock</span>
              <AlertTriangle className="size-5 text-primary" />
            </div>
            <p className="text-3xl font-semibold tabular-nums">
              {loading
                ? "—"
                : (summary?.low_stock_count ?? lowStockItems.length)}
            </p>
          </Link>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Quick actions</h2>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7">
          {SHORTCUTS.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.href + item.label}
                href={item.href}
                className={cn(
                  buttonVariants({
                    variant: "primary" in item && item.primary ? "default" : "outline",
                  }),
                  "min-h-14 flex-col gap-1 text-xs sm:text-sm",
                )}
              >
                <Icon className="size-5" />
                {item.label}
              </Link>
            );
          })}
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
        <section className="space-y-3">
          <div className="flex items-end justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold">Open jobs</h2>
              <p className="text-xs text-muted-foreground">
                In progress and awaiting payment — tap a row
              </p>
            </div>
            <Link
              href="/jobs?status=OPEN"
              className={cn(
                buttonVariants({ variant: "ghost", size: "sm" }),
                "min-h-9",
              )}
            >
              View all
            </Link>
          </div>
          <div className="overflow-x-auto rounded-xl border bg-card">
            <table className="w-full min-w-[560px] text-left text-sm">
              <thead className="border-b bg-muted/40">
                <tr>
                  <th className="px-3 py-3">Plate</th>
                  <th className="px-3 py-3">Customer</th>
                  <th className="px-3 py-3">Status</th>
                  <th className="px-3 py-3">Started</th>
                </tr>
              </thead>
              <tbody>
                {queuePreview.map((job) => (
                  <tr
                    key={job.id}
                    role="link"
                    tabIndex={0}
                    className="cursor-pointer border-b last:border-0 hover:bg-muted/40"
                    onClick={() => router.push(`/jobs/${job.id}`)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        router.push(`/jobs/${job.id}`);
                      }
                    }}
                  >
                    <td className="px-3 py-2.5">
                      <p className="font-semibold">
                        {job.plate_number?.trim() || "No plate"}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {job.document_number}
                      </p>
                    </td>
                    <td className="px-3 py-2.5">
                      {job.customer_name || "—"}
                    </td>
                    <td className="px-3 py-2.5">
                      <Badge variant={statusBadgeVariant(job.status)}>
                        {statusLabel(job.status)}
                      </Badge>
                    </td>
                    <td className="px-3 py-2.5 text-muted-foreground whitespace-nowrap">
                      {formatStarted(job.started_at ?? job.created_at)}
                    </td>
                  </tr>
                ))}
                {!loading && !queuePreview.length ? (
                  <tr>
                    <td
                      colSpan={4}
                      className="px-3 py-8 text-muted-foreground"
                    >
                      No open jobs right now.{" "}
                      <Link href="/jobs/new" className="underline">
                        Start a new job
                      </Link>
                    </td>
                  </tr>
                ) : null}
                {loading ? (
                  <tr>
                    <td
                      colSpan={4}
                      className="px-3 py-8 text-muted-foreground"
                    >
                      Loading jobs…
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </section>

        <section className="space-y-3">
          <div className="flex items-end justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold">Needs attention</h2>
              <p className="text-xs text-muted-foreground">
                Low stock and top commissions today
              </p>
            </div>
          </div>

          <div className="rounded-xl border bg-card p-4">
            <div className="mb-3 flex items-center justify-between">
              <p className="text-sm font-medium">Low stock</p>
              <Link
                href="/inventory"
                className="text-xs text-muted-foreground underline"
              >
                Inventory
              </Link>
            </div>
            {loading ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : lowStockItems.length ? (
              <ul className="space-y-2">
                {lowStockItems.map((p) => (
                  <li
                    key={p.id}
                    className="flex items-center justify-between gap-2 text-sm"
                  >
                    <span className="truncate">{p.name}</span>
                    <span className="shrink-0 tabular-nums text-muted-foreground">
                      {p.stock_qty}/{p.min_stock_threshold}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">
                No low-stock SKUs on this branch.
              </p>
            )}
          </div>

          <div className="rounded-xl border bg-card p-4">
            <div className="mb-3 flex items-center justify-between">
              <p className="text-sm font-medium">Commissions today</p>
              <Link
                href="/reports"
                className="text-xs text-muted-foreground underline"
              >
                Details
              </Link>
            </div>
            {loading ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : summary?.mechanic_commissions?.length ? (
              <ul className="space-y-2">
                {summary.mechanic_commissions.slice(0, 5).map((row) => (
                  <li
                    key={row.mechanic_id}
                    className="flex items-center justify-between gap-2 text-sm"
                  >
                    <Link
                      href={`/mechanics/${row.mechanic_id}`}
                      className="truncate font-medium hover:underline"
                    >
                      {row.nickname}
                    </Link>
                    <span className="shrink-0 tabular-nums">
                      {formatPeso(row.commission_total)}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">
                No commissions recorded yet today.
              </p>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
