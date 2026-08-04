"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SearchableCombobox } from "@/components/ui/searchable-combobox";
import { clientApi, toastError } from "@/lib/client-api";
import type { Paginated, Transaction, TransactionStatus } from "@/lib/types";
import { formatPeso } from "@/lib/types";
import { cn } from "@/lib/utils";

type StatusFilter =
  | "OPEN"
  | "IN_PROGRESS"
  | "DONE"
  | "PAID"
  | "CANCELLED"
  | "ALL";

const STATUS_OPTIONS: { value: StatusFilter; label: string }[] = [
  { value: "OPEN", label: "Open (in progress + awaiting pay)" },
  { value: "IN_PROGRESS", label: "In progress" },
  { value: "DONE", label: "Awaiting pay" },
  { value: "PAID", label: "Paid" },
  { value: "CANCELLED", label: "Cancelled" },
  { value: "ALL", label: "All statuses" },
];

function parseStatusFilter(value: string | null): StatusFilter {
  if (!value) return "OPEN";
  const match = STATUS_OPTIONS.find((o) => o.value === value);
  return match ? match.value : "OPEN";
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

function statusBadgeVariant(
  status: TransactionStatus,
): "default" | "secondary" | "outline" | "destructive" {
  if (status === "IN_PROGRESS") return "default";
  if (status === "DONE") return "secondary";
  if (status === "CANCELLED") return "destructive";
  return "outline";
}

function statusLabel(status: TransactionStatus) {
  if (status === "DONE") return "Awaiting pay";
  if (status === "IN_PROGRESS") return "In progress";
  return status.charAt(0) + status.slice(1).toLowerCase();
}

function matchesSearch(job: Transaction, q: string) {
  const term = q.trim().toLowerCase();
  if (!term) return true;
  const haystack = [
    job.document_number,
    job.plate_number,
    job.customer_name,
    job.customer_phone,
    job.motorcycle_model,
    job.motorcycle_color,
    job.diagnosis_notes,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return haystack.includes(term);
}

function JobsBoardInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [jobs, setJobs] = useState<Transaction[]>([]);
  const [q, setQ] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>(() =>
    parseStatusFilter(searchParams.get("status")),
  );
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setStatusFilter(parseStatusFilter(searchParams.get("status")));
  }, [searchParams]);

  function updateStatusFilter(next: StatusFilter) {
    setStatusFilter(next);
    const params = new URLSearchParams(searchParams.toString());
    if (next === "OPEN") params.delete("status");
    else params.set("status", next);
    const qs = params.toString();
    router.replace(qs ? `/jobs?${qs}` : "/jobs");
  }

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const base = "transaction_type=SERVICE_JOB&page_size=100";
      if (statusFilter === "OPEN") {
        const [a, b] = await Promise.all([
          clientApi<Paginated<Transaction>>(
            `/transactions?${base}&status=IN_PROGRESS`,
          ),
          clientApi<Paginated<Transaction>>(
            `/transactions?${base}&status=DONE`,
          ),
        ]);
        setJobs(
          [...a.items, ...b.items].sort((x, y) => {
            const ax = x.started_at ?? x.created_at;
            const bx = y.started_at ?? y.created_at;
            return bx.localeCompare(ax);
          }),
        );
      } else if (statusFilter === "ALL") {
        const res = await clientApi<Paginated<Transaction>>(
          `/transactions?${base}`,
        );
        setJobs(res.items);
      } else {
        const res = await clientApi<Paginated<Transaction>>(
          `/transactions?${base}&status=${statusFilter}`,
        );
        setJobs(res.items);
      }
    } catch (err) {
      toastError(err);
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const filtered = useMemo(
    () => jobs.filter((job) => matchesSearch(job, q)),
    [jobs, q],
  );

  const counts = useMemo(() => {
    const open = jobs.filter(
      (j) => j.status === "IN_PROGRESS" || j.status === "DONE",
    ).length;
    return {
      shown: filtered.length,
      total: jobs.length,
      open,
    };
  }, [jobs, filtered]);

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Job board</h1>
          <p className="text-sm text-muted-foreground">
            Dense list for busy bays — filter and search, then tap a row
          </p>
        </div>
        <Link href="/jobs/new" className={cn(buttonVariants(), "min-h-11")}>
          New job
        </Link>
      </div>

      <div className="flex flex-col gap-2 lg:flex-row">
        <Input
          className="min-h-11 flex-1"
          placeholder="Search plate, customer, phone, JO#, or notes"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <SearchableCombobox
          className="lg:w-72"
          value={statusFilter}
          onValueChange={(v) => updateStatusFilter(v as StatusFilter)}
          placeholder="Filter status"
          searchPlaceholder="Status…"
          options={STATUS_OPTIONS.map((o) => ({
            value: o.value,
            label: o.label,
          }))}
        />
        <Button className="min-h-11" variant="outline" onClick={load}>
          Refresh
        </Button>
      </div>

      <p className="text-xs text-muted-foreground">
        Showing {counts.shown}
        {q.trim() ? ` of ${counts.total} loaded` : ""} jobs
        {statusFilter === "OPEN" ? " · open bay work" : ""}
      </p>

      <div className="overflow-x-auto rounded-xl border bg-card">
        <table className="w-full min-w-[880px] text-left text-sm">
          <thead className="border-b bg-muted/40">
            <tr>
              <th className="px-3 py-3">Plate</th>
              <th className="px-3 py-3">JO#</th>
              <th className="px-3 py-3">Customer</th>
              <th className="px-3 py-3">Phone</th>
              <th className="px-3 py-3">Bike</th>
              <th className="px-3 py-3">Status</th>
              <th className="px-3 py-3">Started</th>
              <th className="px-3 py-3 text-right">Total</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((job) => {
              const bike = [job.motorcycle_model, job.motorcycle_color]
                .filter(Boolean)
                .join(" · ");
              const href = `/jobs/${job.id}`;
              return (
                <tr
                  key={job.id}
                  role="link"
                  tabIndex={0}
                  className="cursor-pointer border-b last:border-0 hover:bg-muted/40 focus-visible:bg-muted/40 focus-visible:outline-none"
                  onClick={() => router.push(href)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      router.push(href);
                    }
                  }}
                >
                  <td className="px-3 py-2.5">
                    <span className="font-semibold">
                      {job.plate_number?.trim() || "No plate"}
                    </span>
                    {job.diagnosis_notes?.trim() ? (
                      <p className="line-clamp-1 text-xs text-muted-foreground">
                        {job.diagnosis_notes}
                      </p>
                    ) : null}
                  </td>
                  <td className="px-3 py-2.5 text-muted-foreground">
                    {job.document_number}
                  </td>
                  <td className="px-3 py-2.5">{job.customer_name || "—"}</td>
                  <td className="px-3 py-2.5 text-muted-foreground">
                    {job.customer_phone || "—"}
                  </td>
                  <td className="px-3 py-2.5 text-muted-foreground">
                    {bike || "—"}
                  </td>
                  <td className="px-3 py-2.5">
                    <Badge variant={statusBadgeVariant(job.status)}>
                      {statusLabel(job.status)}
                    </Badge>
                  </td>
                  <td className="px-3 py-2.5 text-muted-foreground whitespace-nowrap">
                    {formatStarted(job.started_at)}
                  </td>
                  <td className="px-3 py-2.5 text-right tabular-nums">
                    {job.totals ? formatPeso(job.totals.net_total) : "—"}
                  </td>
                </tr>
              );
            })}
            {!loading && !filtered.length ? (
              <tr>
                <td colSpan={8} className="px-3 py-8 text-muted-foreground">
                  {q.trim()
                    ? "No jobs match this search."
                    : "No jobs for this filter."}
                </td>
              </tr>
            ) : null}
            {loading ? (
              <tr>
                <td colSpan={8} className="px-3 py-8 text-muted-foreground">
                  Loading jobs…
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function JobsPage() {
  return (
    <Suspense fallback={<p className="text-sm text-muted-foreground">Loading…</p>}>
      <JobsBoardInner />
    </Suspense>
  );
}
