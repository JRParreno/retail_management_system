"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";

import { DateRangeFilter } from "@/components/mechanics/date-range-filter";
import { clientApi, toastError } from "@/lib/client-api";
import { mechanicLaborHref, todayISO } from "@/lib/dates";
import type { MechanicLaborBoard } from "@/lib/types";
import { formatPeso } from "@/lib/types";

function parseDateParam(value: string | null, fallback: string) {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return fallback;
  return value;
}

function MechanicLaborBoardInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const today = todayISO();
  const [start, setStart] = useState(() =>
    parseDateParam(searchParams.get("start"), today),
  );
  const [end, setEnd] = useState(() =>
    parseDateParam(searchParams.get("end"), today),
  );
  const [board, setBoard] = useState<MechanicLaborBoard | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (s = start, e = end) => {
    setLoading(true);
    try {
      const data = await clientApi<MechanicLaborBoard>(
        `/mechanics/labor-board?start_date=${s}&end_date=${e}`,
      );
      setBoard(data);
      const params = new URLSearchParams();
      params.set("start", s);
      params.set("end", e);
      router.replace(`/mechanic-labor?${params.toString()}`);
    } catch (err) {
      toastError(err);
    } finally {
      setLoading(false);
    }
  }, [end, router, start]);

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Mechanic labor</h1>
        <p className="text-sm text-muted-foreground">
          All mechanics with labor totals. Tap a mechanic to see every job in
          the date range.
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
            {loading || !board ? "—" : formatPeso(board.labor_total)}
          </p>
        </div>
        <div className="rounded-xl border bg-card px-4 py-3">
          <p className="text-xs text-muted-foreground">Labor lines</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums">
            {loading || !board ? "—" : board.line_count}
          </p>
        </div>
        <div className="rounded-xl border bg-card px-4 py-3">
          <p className="text-xs text-muted-foreground">Jobs</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums">
            {loading || !board ? "—" : board.job_count}
          </p>
        </div>
      </div>

      <div className="overflow-x-auto rounded-xl border bg-card">
        <table className="w-full min-w-[560px] text-left text-sm">
          <thead className="border-b bg-muted/40">
            <tr>
              <th className="px-3 py-3">Mechanic</th>
              <th className="px-3 py-3">Jobs</th>
              <th className="px-3 py-3">Lines</th>
              <th className="px-3 py-3 text-right">Labor total</th>
            </tr>
          </thead>
          <tbody>
            {(board?.mechanics ?? []).map((row) => (
              <tr
                key={row.mechanic_id ?? "unassigned"}
                role="button"
                tabIndex={0}
                className="cursor-pointer border-b last:border-0 transition-colors hover:bg-muted/40"
                onClick={() =>
                  router.push(mechanicLaborHref(row.mechanic_id, start, end))
                }
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    router.push(mechanicLaborHref(row.mechanic_id, start, end));
                  }
                }}
              >
                <td className="px-3 py-3">
                  <span className="block font-medium">{row.nickname}</span>
                  <span className="block text-xs text-muted-foreground">
                    {row.full_name}
                    {!row.is_active ? " · Inactive" : ""}
                  </span>
                </td>
                <td className="px-3 py-3 tabular-nums">{row.job_count}</td>
                <td className="px-3 py-3 tabular-nums">{row.line_count}</td>
                <td className="px-3 py-3 text-right tabular-nums font-semibold">
                  {formatPeso(row.labor_total)}
                </td>
              </tr>
            ))}
            {loading ? (
              <tr>
                <td colSpan={4} className="px-3 py-6 text-muted-foreground">
                  Loading mechanic labor…
                </td>
              </tr>
            ) : null}
            {!loading && !board?.mechanics.length ? (
              <tr>
                <td colSpan={4} className="px-3 py-6 text-muted-foreground">
                  No mechanic labor in this period for the active branch.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function MechanicLaborPage() {
  return (
    <Suspense fallback={<p className="text-sm text-muted-foreground">Loading…</p>}>
      <MechanicLaborBoardInner />
    </Suspense>
  );
}
