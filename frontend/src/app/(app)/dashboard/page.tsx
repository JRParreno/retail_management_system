"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ClipboardList, Package, ShoppingCart, AlertTriangle } from "lucide-react";

import { Button, buttonVariants } from "@/components/ui/button";
import { clientApi, toastError } from "@/lib/client-api";
import type { CashierShift, Paginated, Product, Transaction } from "@/lib/types";
import { cn } from "@/lib/utils";

export default function DashboardPage() {
  const [openJobs, setOpenJobs] = useState(0);
  const [awaitingPay, setAwaitingPay] = useState(0);
  const [lowStock, setLowStock] = useState(0);
  const [shift, setShift] = useState<CashierShift | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [inProgress, done, products, currentShift] = await Promise.all([
          clientApi<Paginated<Transaction>>(
            "/transactions?status=IN_PROGRESS&page_size=1",
          ),
          clientApi<Paginated<Transaction>>("/transactions?status=DONE&page_size=1"),
          clientApi<Paginated<Product>>("/products?page_size=100"),
          clientApi<CashierShift | null>("/shifts/current").catch(() => null),
        ]);
        setOpenJobs(inProgress.total);
        setAwaitingPay(done.total);
        setLowStock(
          products.items.filter((p) => p.stock_qty <= p.min_stock_threshold).length,
        );
        setShift(currentShift);
      } catch (err) {
        toastError(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

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

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Shop floor overview — optimized for tablet POS
        </p>
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

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[
          {
            label: "In progress",
            value: openJobs,
            href: "/jobs",
            icon: ClipboardList,
          },
          {
            label: "Awaiting payment",
            value: awaitingPay,
            href: "/jobs?tab=done",
            icon: ShoppingCart,
          },
          {
            label: "Low stock",
            value: lowStock,
            href: "/inventory",
            icon: AlertTriangle,
          },
          {
            label: "Inventory",
            value: "Parts",
            href: "/inventory",
            icon: Package,
            subtitle: "Search & adjust",
          },
        ].map((card) => {
          const Icon = card.icon;
          return (
            <Link
              key={card.label}
              href={card.href}
              className="rounded-xl border bg-card p-4 transition-colors hover:border-primary/40"
            >
              <div className="mb-3 flex items-center justify-between">
                <span className="text-sm text-muted-foreground">{card.label}</span>
                <Icon className="size-5 text-primary" />
              </div>
              <p className="text-3xl font-semibold tabular-nums">
                {loading ? "—" : card.value}
              </p>
              {"subtitle" in card && card.subtitle ? (
                <p className="mt-1 text-xs text-muted-foreground">{card.subtitle}</p>
              ) : null}
            </Link>
          );
        })}
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <Link
          href="/jobs/new"
          className={cn(buttonVariants(), "min-h-14 justify-center text-base")}
        >
          New service job
        </Link>
        <Link
          href="/pos"
          className={cn(
            buttonVariants({ variant: "secondary" }),
            "min-h-14 justify-center text-base",
          )}
        >
          Direct sale POS
        </Link>
      </div>
    </div>
  );
}
