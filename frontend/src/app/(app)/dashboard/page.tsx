"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Calculator,
  ClipboardList,
  Package,
  Receipt,
  RefreshCw,
  RotateCcw,
  ShoppingCart,
  Wrench,
} from "lucide-react";

import { useBranch } from "@/components/branch/branch-context";
import { useShop } from "@/components/shop/shop-context";
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

function isSameLocalDay(value: string | null | undefined, dayISO: string) {
  if (!value) return false;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return false;
  const local = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const y = local.getFullYear();
  const m = String(local.getMonth() + 1).padStart(2, "0");
  const day = String(local.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}` === dayISO;
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

const SECONDARY_ACTIONS: {
  href: string;
  label: string;
  icon: typeof ClipboardList;
  adminOnly?: boolean;
}[] = [
  { href: "/estimates", label: "Estimate", icon: Calculator },
  { href: "/jobs", label: "Job board", icon: ClipboardList },
  { href: "/direct-sales", label: "Sale history", icon: ShoppingCart },
  { href: "/inventory", label: "Inventory", icon: Package },
  { href: "/refunds", label: "Refunds", icon: RotateCcw },
  { href: "/mechanics", label: "Mechanics", icon: Wrench, adminOnly: true },
  { href: "/reports", label: "Reports", icon: Receipt, adminOnly: true },
];

export default function DashboardPage() {
  const router = useRouter();
  const { activeBranch, user } = useBranch();
  const { settings } = useShop();
  const isAdmin = user?.role === "ADMIN";
  const [summary, setSummary] = useState<ReportSummary | null>(null);
  const [activeJobs, setActiveJobs] = useState<Transaction[]>([]);
  const [directSalesToday, setDirectSalesToday] = useState<Transaction[]>([]);
  const [inProgressCount, setInProgressCount] = useState(0);
  const [awaitingPayCount, setAwaitingPayCount] = useState(0);
  const [lowStockItems, setLowStockItems] = useState<Product[]>([]);
  const [shift, setShift] = useState<CashierShift | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const today = todayISO();
    try {
      const [report, inProgress, awaitingPay, directSales, products, currentShift] =
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
          clientApi<Paginated<Transaction>>(
            "/transactions?transaction_type=DIRECT_SALE&status=PAID&page_size=50",
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
      setDirectSalesToday(
        directSales.items
          .filter((sale) =>
            isSameLocalDay(sale.paid_at ?? sale.created_at, today),
          )
          .sort((a, b) => {
            const ax = a.paid_at ?? a.created_at;
            const bx = b.paid_at ?? b.created_at;
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
  const directSalesPreview = useMemo(
    () => directSalesToday.slice(0, 8),
    [directSalesToday],
  );
  const directSalesTotal = useMemo(
    () =>
      directSalesToday.reduce(
        (sum, sale) => sum + Number(sale.totals?.net_total ?? 0),
        0,
      ),
    [directSalesToday],
  );
  const shiftOpen = shift?.status === "OPEN";
  const lowStockCount = summary?.low_stock_count ?? lowStockItems.length;
  const openJobCount = inProgressCount + awaitingPayCount;

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <h1 className="truncate text-2xl font-semibold tracking-tight">
            {settings.business_name}
          </h1>
          <p className="text-sm text-muted-foreground">
            {activeBranch?.name ?? "Branch"} · floor board
            {!loading ? ` · ${openJobCount} open job${openJobCount === 1 ? "" : "s"}` : ""}
          </p>
        </div>
        <Button
          className="min-h-11 gap-2"
          variant="outline"
          onClick={load}
          disabled={loading}
        >
          <RefreshCw className={cn("size-4", loading && "animate-spin")} />
          Refresh
        </Button>
      </div>

      {!loading && !shiftOpen ? (
        <div className="flex flex-col gap-3 rounded-xl border border-amber-500/40 bg-amber-500/10 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="font-medium text-amber-950 dark:text-amber-100">
              Shift is closed
            </p>
            <p className="text-sm text-amber-950/80 dark:text-amber-100/80">
              Open a cashier shift before collecting payments or deposits.
            </p>
          </div>
          <Button className="min-h-11 shrink-0" onClick={openShift}>
            Open shift
          </Button>
        </div>
      ) : null}

      {shiftOpen ? (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border bg-card px-4 py-3 text-sm">
          <p>
            <span className="font-medium">Shift open</span>
            <span className="text-muted-foreground">
              {" "}
              since {new Date(shift!.opened_at).toLocaleTimeString("en-PH")}
            </span>
          </p>
          <Link
            href="/shifts"
            className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "min-h-9")}
          >
            Manage shift
          </Link>
        </div>
      ) : null}

      <section className="grid gap-2 sm:grid-cols-2">
        <Link
          href="/jobs/new"
          className={cn(
            buttonVariants(),
            "min-h-16 justify-start gap-3 px-4 text-base",
          )}
        >
          <ClipboardList className="size-6 shrink-0" />
          <span className="text-left">
            <span className="block font-semibold">New job</span>
            <span className="block text-xs font-normal opacity-90">
              Start a service bay job
            </span>
          </span>
        </Link>
        <Link
          href="/pos"
          className={cn(
            buttonVariants({ variant: "outline" }),
            "min-h-16 justify-start gap-3 px-4 text-base",
          )}
        >
          <ShoppingCart className="size-6 shrink-0" />
          <span className="text-left">
            <span className="block font-semibold">Direct sale</span>
            <span className="block text-xs font-normal text-muted-foreground">
              Counter checkout / parts only
            </span>
          </span>
        </Link>
      </section>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
        <Link
          href="/jobs?status=IN_PROGRESS"
          className="rounded-xl border bg-card px-3 py-3 transition-colors hover:border-primary/40"
        >
          <p className="text-xs text-muted-foreground">In progress</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums">
            {loading ? "—" : inProgressCount}
          </p>
        </Link>
        <Link
          href="/jobs?status=DONE"
          className="rounded-xl border bg-card px-3 py-3 transition-colors hover:border-primary/40"
        >
          <p className="text-xs text-muted-foreground">Awaiting pay</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums">
            {loading ? "—" : awaitingPayCount}
          </p>
        </Link>
        <Link
          href="/direct-sales"
          className="rounded-xl border bg-card px-3 py-3 transition-colors hover:border-primary/40"
        >
          <p className="text-xs text-muted-foreground">Direct sales</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums">
            {loading ? "—" : directSalesToday.length}
          </p>
          <p className="mt-0.5 text-xs tabular-nums text-muted-foreground">
            {loading ? "—" : formatPeso(directSalesTotal)} today
          </p>
        </Link>
        <Link
          href="/inventory"
          className="rounded-xl border bg-card px-3 py-3 transition-colors hover:border-primary/40"
        >
          <p className="flex items-center gap-1 text-xs text-muted-foreground">
            Low stock
            {!loading && lowStockCount > 0 ? (
              <AlertTriangle className="size-3.5 text-amber-600" />
            ) : null}
          </p>
          <p className="mt-1 text-2xl font-semibold tabular-nums">
            {loading ? "—" : lowStockCount}
          </p>
        </Link>
        {isAdmin ? (
          <Link
            href="/reports"
            className="rounded-xl border bg-card px-3 py-3 transition-colors hover:border-primary/40"
          >
            <p className="text-xs text-muted-foreground">Today sales</p>
            <p className="mt-1 text-xl font-semibold tabular-nums sm:text-2xl">
              {loading || !summary ? "—" : formatPeso(summary.gross_revenue)}
            </p>
          </Link>
        ) : (
          <div className="rounded-xl border bg-card px-3 py-3">
            <p className="text-xs text-muted-foreground">Today sales</p>
            <p className="mt-1 text-xl font-semibold tabular-nums sm:text-2xl">
              {loading || !summary ? "—" : formatPeso(summary.gross_revenue)}
            </p>
          </div>
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        {SECONDARY_ACTIONS.filter((item) => isAdmin || !item.adminOnly).map(
          (item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  buttonVariants({ variant: "secondary" }),
                  "min-h-11 gap-2",
                )}
              >
                <Icon className="size-4" />
                {item.label}
              </Link>
            );
          },
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.5fr_1fr]">
        <div className="space-y-4">
          <section className="rounded-xl border bg-card">
            <div className="flex items-center justify-between gap-3 border-b px-4 py-3">
              <div>
                <h2 className="font-semibold">Open jobs</h2>
                <p className="text-xs text-muted-foreground">
                  Tap a job to open it
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

            <ul className="divide-y">
              {queuePreview.map((job) => (
                <li key={job.id}>
                  <button
                    type="button"
                    className="flex w-full items-start justify-between gap-3 px-4 py-3 text-left transition-colors hover:bg-muted/40"
                    onClick={() => router.push(`/jobs/${job.id}`)}
                  >
                    <span className="min-w-0">
                      <span className="block truncate font-semibold">
                        {job.plate_number?.trim() ||
                          job.motorcycle_model ||
                          "No plate"}
                      </span>
                      <span className="block truncate text-sm text-muted-foreground">
                        {job.customer_name || "Walk-in"} · {job.document_number}
                      </span>
                      <span className="mt-1 block text-xs text-muted-foreground">
                        {formatStarted(job.started_at ?? job.created_at)}
                      </span>
                    </span>
                    <Badge
                      variant={statusBadgeVariant(job.status)}
                      className="shrink-0"
                    >
                      {statusLabel(job.status)}
                    </Badge>
                  </button>
                </li>
              ))}

              {!loading && !queuePreview.length ? (
                <li className="px-4 py-8 text-sm text-muted-foreground">
                  No open jobs.{" "}
                  <Link
                    href="/jobs/new"
                    className="font-medium text-primary underline"
                  >
                    Start a new job
                  </Link>
                </li>
              ) : null}

              {loading ? (
                <li className="px-4 py-8 text-sm text-muted-foreground">
                  Loading jobs…
                </li>
              ) : null}
            </ul>
          </section>

          <section className="rounded-xl border bg-card">
            <div className="flex items-center justify-between gap-3 border-b px-4 py-3">
              <div>
                <h2 className="font-semibold">Direct sales today</h2>
                <p className="text-xs text-muted-foreground">
                  Counter checkouts ·{" "}
                  {loading ? "—" : formatPeso(directSalesTotal)}
                </p>
              </div>
              <Link
                href="/direct-sales"
                className={cn(
                  buttonVariants({ variant: "ghost", size: "sm" }),
                  "min-h-9",
                )}
              >
                View all
              </Link>
            </div>

            <ul className="divide-y">
              {directSalesPreview.map((sale) => {
                const itemCount = sale.part_lines.reduce(
                  (sum, line) => sum + line.quantity,
                  0,
                );
                return (
                  <li key={sale.id}>
                    <button
                      type="button"
                      className="flex w-full items-start justify-between gap-3 px-4 py-3 text-left transition-colors hover:bg-muted/40"
                      onClick={() => router.push(`/jobs/${sale.id}`)}
                    >
                      <span className="min-w-0">
                        <span className="block truncate font-semibold">
                          {sale.document_number}
                        </span>
                        <span className="block truncate text-sm text-muted-foreground">
                          {itemCount} item{itemCount === 1 ? "" : "s"}
                          {sale.customer_name
                            ? ` · ${sale.customer_name}`
                            : ""}
                        </span>
                        <span className="mt-1 block text-xs text-muted-foreground">
                          {formatStarted(sale.paid_at ?? sale.created_at)}
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
                    </button>
                  </li>
                );
              })}

              {!loading && !directSalesPreview.length ? (
                <li className="px-4 py-8 text-sm text-muted-foreground">
                  No direct sales yet today.{" "}
                  <Link
                    href="/pos"
                    className="font-medium text-primary underline"
                  >
                    Open counter checkout
                  </Link>
                </li>
              ) : null}

              {loading ? (
                <li className="px-4 py-8 text-sm text-muted-foreground">
                  Loading sales…
                </li>
              ) : null}
            </ul>
          </section>
        </div>

        <div className="space-y-4">
          {isAdmin ? (
            <section className="rounded-xl border bg-card p-4">
              <div className="mb-3 flex items-center justify-between gap-2">
                <h2 className="font-semibold">Today at a glance</h2>
                <Link
                  href="/reports"
                  className="text-xs text-muted-foreground underline"
                >
                  Full reports
                </Link>
              </div>
              <dl className="space-y-2 text-sm">
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Gross</dt>
                  <dd className="tabular-nums font-medium">
                    {loading || !summary
                      ? "—"
                      : formatPeso(summary.gross_revenue)}
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Direct sales</dt>
                  <dd className="tabular-nums font-medium">
                    {loading
                      ? "—"
                      : `${directSalesToday.length} · ${formatPeso(directSalesTotal)}`}
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Net profit</dt>
                  <dd className="tabular-nums font-medium">
                    {loading || !summary
                      ? "—"
                      : formatPeso(summary.net_profit)}
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Tickets</dt>
                  <dd className="tabular-nums font-medium">
                    {loading || !summary ? "—" : summary.transaction_count}
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Avg ticket</dt>
                  <dd className="tabular-nums font-medium">
                    {loading || !summary
                      ? "—"
                      : formatPeso(summary.avg_ticket)}
                  </dd>
                </div>
              </dl>
              {summary && !loading ? (
                <p className="mt-3 border-t pt-3 text-xs text-muted-foreground">
                  Parts {formatPeso(summary.parts_sales)} · Labor{" "}
                  {formatPeso(summary.labor_sales)} · Commission{" "}
                  {formatPeso(summary.commission_total)}
                </p>
              ) : null}
            </section>
          ) : null}

          <section className="rounded-xl border bg-card p-4">
            <div className="mb-3 flex items-center justify-between gap-2">
              <h2 className="font-semibold">
                {isAdmin ? "Needs attention" : "Low stock"}
              </h2>
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
                    <span className="shrink-0 tabular-nums text-amber-700 dark:text-amber-300">
                      {p.stock_qty}/{p.min_stock_threshold}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">
                Stock levels look fine on this branch.
              </p>
            )}

            {isAdmin ? (
              <div className="mt-4 border-t pt-3">
                <div className="mb-2 flex items-center justify-between">
                  <p className="text-sm font-medium">Commissions today</p>
                  <Link
                    href="/reports"
                    className="text-xs text-muted-foreground underline"
                  >
                    Details
                  </Link>
                </div>
                {summary?.mechanic_commissions?.length ? (
                  <ul className="space-y-2">
                    {summary.mechanic_commissions.slice(0, 4).map((row) => (
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
                    No commissions yet today.
                  </p>
                )}
              </div>
            ) : null}
          </section>
        </div>
      </div>
    </div>
  );
}
