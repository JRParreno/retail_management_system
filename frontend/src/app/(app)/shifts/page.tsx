"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { clientApi, toastError } from "@/lib/client-api";
import type { CashierShift } from "@/lib/types";
import { formatPeso } from "@/lib/types";

export default function ShiftsPage() {
  const [shift, setShift] = useState<CashierShift | null>(null);
  const [floatAmt, setFloatAmt] = useState("0");
  const [counted, setCounted] = useState("");

  async function load() {
    try {
      const current = await clientApi<CashierShift | null>("/shifts/current");
      setShift(current);
    } catch (err) {
      toastError(err);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function openShift() {
    try {
      const s = await clientApi<CashierShift>("/shifts/open", {
        method: "POST",
        body: JSON.stringify({ opening_float: floatAmt || "0" }),
      });
      setShift(s);
    } catch (err) {
      toastError(err);
    }
  }

  async function closeShift() {
    if (!shift) return;
    try {
      const s = await clientApi<CashierShift>(`/shifts/${shift.id}/close`, {
        method: "POST",
        body: JSON.stringify({ closing_cash_counted: counted || "0" }),
      });
      setShift(s);
    } catch (err) {
      toastError(err);
    }
  }

  return (
    <div className="mx-auto max-w-lg space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Cashier shift</h1>
        <p className="text-sm text-muted-foreground">Open float and close drawer</p>
      </div>

      <div className="rounded-xl border bg-card p-4 space-y-4">
        {shift?.status === "OPEN" ? (
          <>
            <p>
              Shift open since{" "}
              <strong>{new Date(shift.opened_at).toLocaleString("en-PH")}</strong>
            </p>
            <p className="text-sm text-muted-foreground">
              Opening float: {formatPeso(shift.opening_float)}
            </p>
            <div className="space-y-2">
              <Label>Closing cash counted</Label>
              <Input
                className="min-h-11"
                value={counted}
                onChange={(e) => setCounted(e.target.value)}
              />
            </div>
            <Button className="min-h-11 w-full" onClick={closeShift}>
              Close shift
            </Button>
          </>
        ) : (
          <>
            <p className="text-sm text-muted-foreground">No open shift.</p>
            <div className="space-y-2">
              <Label>Opening float</Label>
              <Input
                className="min-h-11"
                value={floatAmt}
                onChange={(e) => setFloatAmt(e.target.value)}
              />
            </div>
            <Button className="min-h-11 w-full" onClick={openShift}>
              Open shift
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
