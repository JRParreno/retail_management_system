"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { useShop } from "@/components/shop/shop-context";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { clientApi, toastError } from "@/lib/client-api";
import type {
  CashierShift,
  CommissionComputationReport,
  Mechanic,
} from "@/lib/types";
import { formatPeso } from "@/lib/types";

function formatTime(iso: string | null | undefined) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-PH", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatClock(iso: string | null | undefined) {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("en-PH", {
    hour: "numeric",
    minute: "2-digit",
  });
}

function suggestTiming(
  scheduledEndAt: string | null,
): "ON_TIME" | "EARLY" | "EXTENDED" {
  if (!scheduledEndAt) return "ON_TIME";
  const deltaMin =
    (Date.now() - new Date(scheduledEndAt).getTime()) / (60 * 1000);
  if (deltaMin < -15) return "EARLY";
  if (deltaMin > 15) return "EXTENDED";
  return "ON_TIME";
}

function openedEarly(openedAt: string, shiftStartHhmm: string): boolean {
  const opened = new Date(openedAt);
  const [h, m] = shiftStartHhmm.split(":").map(Number);
  const scheduled = new Date(opened);
  scheduled.setHours(h || 0, m || 0, 0, 0);
  return opened.getTime() < scheduled.getTime() - 15 * 60 * 1000;
}

export default function ShiftsPage() {
  const { settings } = useShop();
  const [shift, setShift] = useState<CashierShift | null>(null);
  const [endTime, setEndTime] = useState(settings.cashier_shift_end || "17:00");
  const [counted, setCounted] = useState("0");
  const [timing, setTiming] = useState<"ON_TIME" | "EARLY" | "EXTENDED">(
    "ON_TIME",
  );
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [mechanics, setMechanics] = useState<Mechanic[]>([]);
  const [firstMechanicId, setFirstMechanicId] = useState<string>("");
  const [report, setReport] = useState<CommissionComputationReport | null>(
    null,
  );

  const loadReport = useCallback(
    async (mechanicId?: string) => {
      try {
        const params = new URLSearchParams();
        const mid = mechanicId || firstMechanicId;
        if (mid) params.set("first_mechanic_id", mid);
        const qs = params.toString();
        const data = await clientApi<CommissionComputationReport>(
          `/shifts/commission-report${qs ? `?${qs}` : ""}`,
        );
        setReport(data);
        if (!firstMechanicId && data.first_mechanic_id) {
          setFirstMechanicId(data.first_mechanic_id);
        }
        return data;
      } catch (err) {
        toastError(err);
        return null;
      }
    },
    [firstMechanicId],
  );

  async function load() {
    try {
      const [current, mechs] = await Promise.all([
        clientApi<CashierShift | null>("/shifts/current"),
        clientApi<Mechanic[]>("/mechanics"),
      ]);
      setShift(current);
      setMechanics(mechs);
      if (current?.scheduled_end_at) {
        const d = new Date(current.scheduled_end_at);
        const hh = String(d.getHours()).padStart(2, "0");
        const mm = String(d.getMinutes()).padStart(2, "0");
        setEndTime(`${hh}:${mm}`);
        setTiming(suggestTiming(current.scheduled_end_at));
      }
      if (current?.first_mechanic_id) {
        setFirstMechanicId(current.first_mechanic_id);
      }
    } catch (err) {
      toastError(err);
    }
  }

  useEffect(() => {
    setEndTime(settings.cashier_shift_end || "17:00");
  }, [settings.cashier_shift_end]);

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    if (settings.waive_first_mechanic_commission) {
      void loadReport();
    }
  }, [settings.waive_first_mechanic_commission, loadReport]);

  const scheduleLabel = useMemo(() => {
    const start = settings.cashier_shift_start || "08:00";
    const end = settings.cashier_shift_end || "17:00";
    return `${start} – ${end}`;
  }, [settings.cashier_shift_start, settings.cashier_shift_end]);

  const selectedMechanic = mechanics.find((m) => m.id === firstMechanicId);
  const hasCommissionRows = (report?.mechanics.length ?? 0) > 0;
  const isSettled = hasCommissionRows && !!report?.applied;

  async function openShift() {
    setBusy(true);
    try {
      const s = await clientApi<CashierShift>("/shifts/open", {
        method: "POST",
        body: JSON.stringify({
          opening_float: "0.00",
          scheduled_end_time: endTime,
        }),
      });
      setShift(s);
      setTiming(suggestTiming(s.scheduled_end_at));
      const early = openedEarly(
        s.opened_at,
        settings.cashier_shift_start || "08:00",
      );
      toast.success(
        early
          ? "Shift opened early — expected end saved"
          : "Shift opened — expected end saved",
      );
      if (settings.waive_first_mechanic_commission) {
        await loadReport();
      }
    } catch (err) {
      toastError(err);
    } finally {
      setBusy(false);
    }
  }

  async function settleCommissions() {
    if (!settings.waive_first_mechanic_commission) return;
    setBusy(true);
    try {
      const data = await clientApi<CommissionComputationReport>(
        "/shifts/settle-commissions",
        {
          method: "POST",
          body: JSON.stringify({
            first_mechanic_id: firstMechanicId || null,
          }),
        },
      );
      setReport(data);
      toast.success(
        data.first_mechanic_nickname
          ? `Commission waived for ${data.first_mechanic_nickname} (first mechanic)`
          : "Commissions settled",
      );
    } catch (err) {
      toastError(err);
    } finally {
      setBusy(false);
    }
  }

  async function selectFirstMechanic(mechanicId: string) {
    setFirstMechanicId(mechanicId);
    try {
      if (shift?.status === "OPEN") {
        const updated = await clientApi<CashierShift>(
          "/shifts/current/first-mechanic",
          {
            method: "POST",
            body: JSON.stringify({ mechanic_id: mechanicId }),
          },
        );
        setShift(updated);
        toast.success("Today's zero-commission mechanic saved");
      }
      await loadReport(mechanicId);
    } catch (err) {
      toastError(err);
    }
  }

  async function closeShift() {
    if (!shift) return;
    setBusy(true);
    try {
      let selectedId = firstMechanicId;
      if (settings.waive_first_mechanic_commission) {
        const latest = await loadReport();
        if (!latest) return;
        selectedId = selectedId || latest.first_mechanic_id || "";
        if (latest.mechanics.length > 0 && !selectedId) {
          toast.error(
            "Select today's zero-commission mechanic before closing the shift",
          );
          return;
        }
      }
      const s = await clientApi<CashierShift>(`/shifts/${shift.id}/close`, {
        method: "POST",
        body: JSON.stringify({
          closing_cash_counted: counted || "0",
          close_timing: timing,
          close_notes: notes.trim() || null,
          first_mechanic_id: selectedId || null,
        }),
      });
      setShift(s);
      toast.success(
        timing === "EXTENDED"
          ? "Shift closed (extended)"
          : timing === "EARLY"
            ? "Shift closed (early)"
            : "Shift closed on time",
      );
      if (settings.waive_first_mechanic_commission) {
        await loadReport();
      }
    } catch (err) {
      toastError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Cashier shift</h1>
        <p className="text-sm text-muted-foreground">
          Set your end time for today. You can open early or stay past the usual
          schedule when needed.
        </p>
      </div>

      <div className="rounded-xl border bg-card p-4 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p className="text-xs text-muted-foreground">Shop default schedule</p>
            <p className="font-medium tabular-nums">{scheduleLabel}</p>
          </div>
          {shift?.status === "OPEN" &&
          openedEarly(shift.opened_at, settings.cashier_shift_start || "08:00") ? (
            <Badge>Opened early</Badge>
          ) : null}
        </div>

        {shift?.status === "OPEN" ? (
          <>
            <div className="rounded-lg border bg-muted/30 p-3 text-sm space-y-1">
              <p>
                Opened <strong>{formatTime(shift.opened_at)}</strong>
              </p>
              <p>
                Expected end{" "}
                <strong>{formatClock(shift.scheduled_end_at)}</strong>
              </p>
            </div>

            <div className="space-y-2">
              <Label>Closing status</Label>
              <Select
                value={timing}
                onValueChange={(v) =>
                  setTiming(v as "ON_TIME" | "EARLY" | "EXTENDED")
                }
              >
                <SelectTrigger className="min-h-11">
                  <SelectValue placeholder="Select timing" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ON_TIME">On time</SelectItem>
                  <SelectItem value="EARLY">Closing early</SelectItem>
                  <SelectItem value="EXTENDED">Extended / overtime</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Closing cash counted (optional)</Label>
              <Input
                className="min-h-11"
                inputMode="decimal"
                value={counted}
                onChange={(e) => setCounted(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label>Notes (optional)</Label>
              <Input
                className="min-h-11"
                placeholder="Why early / extended?"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
            </div>

            <Button
              className="min-h-11 w-full"
              onClick={closeShift}
              disabled={
                busy ||
                (settings.waive_first_mechanic_commission &&
                  hasCommissionRows &&
                  !firstMechanicId)
              }
            >
              {busy
                ? "Closing…"
                : settings.waive_first_mechanic_commission &&
                    hasCommissionRows &&
                    !isSettled
                  ? "Settle commissions & close shift"
                  : "Close shift"}
            </Button>
            {settings.waive_first_mechanic_commission &&
            hasCommissionRows &&
            !firstMechanicId ? (
              <p className="text-xs text-destructive">
                Select today&apos;s zero-commission mechanic below before
                closing.
              </p>
            ) : null}
          </>
        ) : (
          <>
            <p className="text-sm text-muted-foreground">
              No open shift. Set when you expect to finish today — use the shop
              default, or move it earlier / later.
            </p>
            <div className="space-y-2">
              <Label htmlFor="end-time">Expected end time</Label>
              <Input
                id="end-time"
                type="time"
                className="min-h-11"
                value={endTime}
                onChange={(e) => setEndTime(e.target.value)}
              />
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  onClick={() =>
                    setEndTime(settings.cashier_shift_end || "17:00")
                  }
                >
                  Use default ({settings.cashier_shift_end || "17:00"})
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    const [h, m] = (endTime || "17:00").split(":").map(Number);
                    const d = new Date();
                    d.setHours(h || 17, (m || 0) + 60, 0, 0);
                    setEndTime(
                      `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`,
                    );
                  }}
                >
                  +1 hour extend
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    const [h, m] = (endTime || "17:00").split(":").map(Number);
                    const d = new Date();
                    d.setHours(h || 17, Math.max(0, (m || 0) - 60), 0, 0);
                    setEndTime(
                      `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`,
                    );
                  }}
                >
                  −1 hour earlier
                </Button>
              </div>
            </div>
            <Button
              className="min-h-11 w-full"
              onClick={openShift}
              disabled={busy}
            >
              {busy ? "Opening…" : "Open shift"}
            </Button>
          </>
        )}
      </div>

      {settings.waive_first_mechanic_commission ? (
        <section className="rounded-xl border bg-card p-4 space-y-4">
          <div>
            <h2 className="font-semibold">Commission settlement</h2>
            <p className="text-sm text-muted-foreground">
              Choose one mechanic each day for zero commission payout. Review
              the computation, then settle before closing the shop.
            </p>
          </div>

          <div className="space-y-2">
            <Label>Today&apos;s zero-commission mechanic</Label>
            <Select
              value={firstMechanicId || undefined}
              onValueChange={(v) => {
                if (v) void selectFirstMechanic(v);
              }}
              disabled={shift?.status !== "OPEN" || isSettled}
            >
              <SelectTrigger className="min-h-11">
                <SelectValue placeholder="Choose mechanic">
                  {selectedMechanic?.nickname ?? "Choose mechanic"}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {mechanics.map((m) => (
                  <SelectItem key={m.id} value={m.id}>
                    {m.nickname}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              {shift?.status === "OPEN"
                ? "Saved for this shift and reset for the next day."
                : "Open today’s cashier shift before choosing a mechanic."}
            </p>
          </div>

          {report ? (
            <div className="overflow-x-auto rounded-lg border">
              <table className="w-full min-w-[520px] text-left text-sm">
                <thead className="border-b bg-muted/40">
                  <tr>
                    <th className="px-3 py-2">Mechanic</th>
                    <th className="px-3 py-2">Labor</th>
                    <th className="px-3 py-2">Gross</th>
                    <th className="px-3 py-2">Waived</th>
                    <th className="px-3 py-2">Net pay</th>
                  </tr>
                </thead>
                <tbody>
                  {report.mechanics.map((row) => (
                    <tr key={row.mechanic_id} className="border-b last:border-0">
                      <td className="px-3 py-2 font-medium">
                        {row.nickname}
                        {row.is_first_mechanic ? (
                          <Badge className="ml-2" variant="secondary">
                            First
                          </Badge>
                        ) : null}
                      </td>
                      <td className="px-3 py-2 tabular-nums">
                        {formatPeso(row.labor_sales)}
                      </td>
                      <td className="px-3 py-2 tabular-nums">
                        {formatPeso(row.commission_gross)}
                      </td>
                      <td className="px-3 py-2 tabular-nums">
                        {formatPeso(row.commission_waived)}
                      </td>
                      <td className="px-3 py-2 tabular-nums font-medium">
                        {formatPeso(row.commission_net)}
                      </td>
                    </tr>
                  ))}
                  {!report.mechanics.length ? (
                    <tr>
                      <td
                        colSpan={5}
                        className="px-3 py-4 text-muted-foreground"
                      >
                        No DONE/PAID labor yet today.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
              <div className="flex flex-wrap gap-3 border-t px-3 py-2 text-xs text-muted-foreground">
                <span>
                  Gross {formatPeso(report.commission_gross_total)}
                </span>
                <span>
                  Waived {formatPeso(report.commission_waived_total)}
                </span>
                <span className="font-medium text-foreground">
                  Net {formatPeso(report.commission_net_total)}
                </span>
                {isSettled ? (
                  <Badge variant="secondary">Settled</Badge>
                ) : null}
              </div>
            </div>
          ) : null}

          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="outline"
              className="min-h-11"
              disabled={busy}
              onClick={() => loadReport()}
            >
              Refresh computation
            </Button>
            <Button
              type="button"
              className="min-h-11"
              disabled={
                busy ||
                isSettled ||
                !hasCommissionRows ||
                !firstMechanicId
              }
              onClick={settleCommissions}
            >
              {isSettled
                ? "Already settled"
                : !hasCommissionRows
                  ? "No commissions to settle"
                  : "Apply first-mechanic waiver"}
            </Button>
          </div>

          {shift?.status === "OPEN" ? (
            <p className="rounded-lg border bg-muted/30 p-3 text-sm text-muted-foreground">
              Commission settlement is applied automatically when you close
              the shift. It cannot be skipped when eligible labor exists.
            </p>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
