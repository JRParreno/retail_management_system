"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { ArrowLeft } from "lucide-react";

import { DateRangeFilter } from "@/components/mechanics/date-range-filter";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { clientApi, toastError } from "@/lib/client-api";
import { dateQuery, formatRangeLabel, todayISO } from "@/lib/dates";
import type { MechanicLaborWork, MechanicLaborWorkLine } from "@/lib/types";
import { formatPeso } from "@/lib/types";
import { cn } from "@/lib/utils";

function parseDateParam(value: string | null, fallback: string) {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return fallback;
  return value;
}

function statusLabel(status: MechanicLaborWorkLine["transaction_status"]) {
  if (status === "DONE") return "Awaiting pay";
  if (status === "IN_PROGRESS") return "In progress";
  if (!status) return "—";
  return status.charAt(0) + status.slice(1).toLowerCase();
}

function statusBadgeVariant(
  status: MechanicLaborWorkLine["transaction_status"],
): "default" | "secondary" | "outline" | "destructive" {
  if (status === "IN_PROGRESS") return "default";
  if (status === "DONE") return "secondary";
  if (status === "CANCELLED") return "destructive";
  return "outline";
}

function MechanicLaborWorkInner() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();
  const today = todayISO();
  const [start, setStart] = useState(() =>
    parseDateParam(searchParams.get("start"), today),
  );
  const [end, setEnd] = useState(() =>
    parseDateParam(searchParams.get("end"), today),
  );
  const [work, setWork] = useState<MechanicLaborWork | null>(null);
  const [selected, setSelected] = useState<MechanicLaborWorkLine | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(
    async (s = start, e = end) => {
      setLoading(true);
      try {
        const path =
          id === "unassigned"
            ? "/mechanics/unassigned/labor-work"
            : `/mechanics/${id}/labor-work`;
        const data = await clientApi<MechanicLaborWork>(
          `${path}?start_date=${s}&end_date=${e}`,
        );
        setWork(data);
        const params = new URLSearchParams();
        params.set("start", s);
        params.set("end", e);
        router.replace(`/mechanic-labor/${id}?${params.toString()}`);
      } catch (err) {
        toastError(err);
      } finally {
        setLoading(false);
      }
    },
    [end, id, router, start],
  );

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const backQs = dateQuery(start, end);

  return (
    <div className="space-y-4">
      <div>
        <Link
          href={`/mechanic-labor?${backQs}`}
          className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" /> Mechanic labor
        </Link>
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-2xl font-semibold tracking-tight">
            {work?.nickname ?? "Mechanic"}
          </h1>
          {work ? (
            <Badge variant={work.is_active ? "secondary" : "outline"}>
              {work.is_active ? "Active" : "Inactive"}
            </Badge>
          ) : null}
        </div>
        <p className="text-sm text-muted-foreground">
          {work?.full_name ?? "Loading work…"}
          {work ? ` · ${formatRangeLabel(start, end)}` : ""}
        </p>
      </div>

      <DateRangeFilter
        start={start}
        end={end}
        onStartChange={setStart}
        onEndChange={setEnd}
        onApply={(s, e) => {
          setStart(s);
          setEnd(e);
          void load(s, e);
        }}
        disabled={loading}
      />

      <div className="grid gap-2 sm:grid-cols-3">
        <div className="rounded-xl border bg-card px-4 py-3">
          <p className="text-xs text-muted-foreground">Labor total</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums">
            {loading || !work ? "—" : formatPeso(work.labor_total)}
          </p>
        </div>
        <div className="rounded-xl border bg-card px-4 py-3">
          <p className="text-xs text-muted-foreground">Jobs</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums">
            {loading || !work ? "—" : work.job_count}
          </p>
        </div>
        <div className="rounded-xl border bg-card px-4 py-3">
          <p className="text-xs text-muted-foreground">Labor lines</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums">
            {loading || !work ? "—" : work.line_count}
          </p>
        </div>
      </div>

      <div className="overflow-x-auto rounded-xl border bg-card">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead className="border-b bg-muted/40">
            <tr>
              <th className="px-3 py-3">Motorcycle</th>
              <th className="px-3 py-3">Service</th>
              <th className="px-3 py-3">Fee</th>
              <th className="px-3 py-3">Status</th>
              <th className="px-3 py-3">When</th>
            </tr>
          </thead>
          <tbody>
            {(work?.lines ?? []).map((line) => (
              <tr
                key={line.id}
                role="button"
                tabIndex={0}
                className="cursor-pointer border-b last:border-0 transition-colors hover:bg-muted/40"
                onClick={() => setSelected(line)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setSelected(line);
                  }
                }}
              >
                <td className="px-3 py-3">
                  <span className="block font-medium">
                    {line.plate_number?.trim() ||
                      line.motorcycle_model ||
                      "No plate"}
                  </span>
                  <span className="block text-xs text-muted-foreground">
                    {[line.motorcycle_model, line.customer_name]
                      .filter((v) => v && String(v).trim())
                      .join(" · ") || "Tap for details"}
                  </span>
                </td>
                <td className="px-3 py-3 font-medium">{line.service_name}</td>
                <td className="px-3 py-3 tabular-nums">
                  {formatPeso(line.actual_price)}
                </td>
                <td className="px-3 py-3">
                  <Badge variant={statusBadgeVariant(line.transaction_status)}>
                    {statusLabel(line.transaction_status)}
                  </Badge>
                </td>
                <td className="px-3 py-3 text-muted-foreground">
                  {new Date(line.created_at).toLocaleString("en-PH")}
                </td>
              </tr>
            ))}
            {loading ? (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-muted-foreground">
                  Loading work…
                </td>
              </tr>
            ) : null}
            {!loading && work && !work.lines.length ? (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-muted-foreground">
                  No labor in this period for the active branch.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      <Dialog
        open={selected != null}
        onOpenChange={(open) => {
          if (!open) setSelected(null);
        }}
      >
        <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Labor details</DialogTitle>
          </DialogHeader>
          {selected ? (
            <div className="space-y-4 text-sm">
              <div>
                <p className="text-xs text-muted-foreground">Motorcycle</p>
                <p className="font-semibold">
                  {selected.plate_number?.trim() ||
                    selected.motorcycle_model ||
                    "No plate"}
                </p>
                <p className="text-muted-foreground">
                  {[selected.motorcycle_model, selected.motorcycle_color]
                    .filter((v) => v && String(v).trim())
                    .join(" · ") || "—"}
                </p>
              </div>

              <div>
                <p className="text-xs text-muted-foreground">Customer</p>
                <p className="font-medium">
                  {selected.customer_name?.trim() || "Walk-in"}
                </p>
                {selected.customer_phone ? (
                  <p className="text-muted-foreground">
                    {selected.customer_phone}
                  </p>
                ) : null}
              </div>

              <div>
                <p className="text-xs text-muted-foreground">Service</p>
                <p className="font-medium">{selected.service_name}</p>
                {selected.description ? (
                  <p className="mt-1 whitespace-pre-wrap text-muted-foreground">
                    {selected.description}
                  </p>
                ) : null}
              </div>

              <dl className="space-y-2 rounded-lg border bg-muted/30 p-3">
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Job</dt>
                  <dd className="font-mono text-xs">
                    {selected.document_number ?? "—"}
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Status</dt>
                  <dd>{statusLabel(selected.transaction_status)}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Labor fee</dt>
                  <dd className="tabular-nums font-medium">
                    {formatPeso(selected.actual_price)}
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Added</dt>
                  <dd>
                    {new Date(selected.created_at).toLocaleString("en-PH")}
                  </dd>
                </div>
              </dl>

              <Link
                href={`/jobs/${selected.transaction_id}`}
                className={cn(
                  buttonVariants(),
                  "min-h-11 w-full justify-center",
                )}
                onClick={() => setSelected(null)}
              >
                Open job
              </Link>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default function MechanicLaborWorkPage() {
  return (
    <Suspense fallback={<p className="text-sm text-muted-foreground">Loading…</p>}>
      <MechanicLaborWorkInner />
    </Suspense>
  );
}
