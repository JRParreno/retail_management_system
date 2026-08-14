"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { DateRangeFilter } from "@/components/mechanics/date-range-filter";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { clientApi, toastError } from "@/lib/client-api";
import { dateQuery, mechanicLaborHref, todayISO } from "@/lib/dates";
import type { MechanicLaborBoard } from "@/lib/types";
import { formatPeso } from "@/lib/types";
import { cn } from "@/lib/utils";

export function MechanicLaborSection() {
  const router = useRouter();
  const [start, setStart] = useState(todayISO());
  const [end, setEnd] = useState(todayISO());
  const [board, setBoard] = useState<MechanicLaborBoard | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (s = start, e = end) => {
    setLoading(true);
    try {
      const data = await clientApi<MechanicLaborBoard>(
        `/mechanics/labor-board?start_date=${s}&end_date=${e}`,
      );
      setBoard(data);
    } catch (err) {
      toastError(err);
    } finally {
      setLoading(false);
    }
  }, [start, end]);

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const qs = dateQuery(start, end);

  return (
    <section className="rounded-xl border bg-card">
      <div className="flex items-center justify-between gap-3 border-b px-4 py-3">
        <div>
          <h2 className="font-semibold">Mechanic labor</h2>
          <p className="text-xs text-muted-foreground">
            Totals by mechanic · tap a row for all work
          </p>
        </div>
        <Link
          href={`/mechanic-labor?${qs}`}
          className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "min-h-9")}
        >
          View all
        </Link>
      </div>

      <div className="border-b px-4 py-3">
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
      </div>

      <ul className="divide-y">
        {(board?.mechanics ?? []).map((row) => (
          <li key={row.mechanic_id ?? "unassigned"}>
            <button
              type="button"
              className="flex w-full items-start justify-between gap-3 px-4 py-3 text-left transition-colors hover:bg-muted/40"
              onClick={() =>
                router.push(mechanicLaborHref(row.mechanic_id, start, end))
              }
            >
              <span className="min-w-0">
                <span className="block truncate font-semibold">
                  {row.nickname}
                </span>
                <span className="block truncate text-sm text-muted-foreground">
                  {row.full_name}
                  {row.job_count
                    ? ` · ${row.job_count} job${row.job_count === 1 ? "" : "s"}`
                    : " · No labor in range"}
                </span>
              </span>
              <span className="shrink-0 text-right">
                <span className="block tabular-nums font-semibold">
                  {formatPeso(row.labor_total)}
                </span>
                {!row.is_active ? (
                  <Badge variant="outline" className="mt-1">
                    Inactive
                  </Badge>
                ) : null}
              </span>
            </button>
          </li>
        ))}

        {loading ? (
          <li className="px-4 py-8 text-sm text-muted-foreground">
            Loading mechanic labor…
          </li>
        ) : null}

        {!loading && !board?.mechanics.length ? (
          <li className="px-4 py-8 text-sm text-muted-foreground">
            No mechanic labor yet for this date range.
          </li>
        ) : null}
      </ul>

      {!loading && board ? (
        <div className="flex items-center justify-between gap-3 border-t px-4 py-3 text-sm">
          <span className="text-muted-foreground">
            {board.line_count} labor line{board.line_count === 1 ? "" : "s"}
          </span>
          <span className="tabular-nums font-semibold">
            {formatPeso(board.labor_total)}
          </span>
        </div>
      ) : null}
    </section>
  );
}
