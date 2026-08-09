"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { useBranch } from "@/components/branch/branch-context";
import { useShop } from "@/components/shop/shop-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { clientApi, toastError } from "@/lib/client-api";
import type { ShopSettings } from "@/lib/types";

const COLOR_PRESETS = [
  { label: "Amber copper", value: "#C26A1A" },
  { label: "Ocean blue", value: "#2563EB" },
  { label: "Forest green", value: "#15803D" },
  { label: "Ruby red", value: "#B91C1C" },
  { label: "Slate gray", value: "#475569" },
] as const;

export default function ShopSettingsPage() {
  const router = useRouter();
  const { user } = useBranch();
  const { settings, applyLocal, refresh } = useShop();
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState<ShopSettings>(settings);

  useEffect(() => {
    if (user && user.role !== "ADMIN") {
      router.replace("/dashboard");
    }
  }, [user, router]);

  useEffect(() => {
    setForm(settings);
  }, [settings]);

  if (!user || user.role !== "ADMIN") {
    return <p className="text-sm text-muted-foreground">Redirecting…</p>;
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const business_name = form.business_name.trim();
    const primary_color = form.primary_color.trim().toUpperCase();
    const cashier_shift_start = (form.cashier_shift_start || "08:00").trim();
    const cashier_shift_end = (form.cashier_shift_end || "17:00").trim();
    const waive_first_mechanic_commission = !!form.waive_first_mechanic_commission;
    if (!business_name) {
      toast.error("Business name is required");
      return;
    }
    if (!/^#[0-9A-F]{6}$/.test(primary_color)) {
      toast.error("Primary color must look like #C26A1A");
      return;
    }
    if (
      !/^([01]\d|2[0-3]):([0-5]\d)$/.test(cashier_shift_start) ||
      !/^([01]\d|2[0-3]):([0-5]\d)$/.test(cashier_shift_end)
    ) {
      toast.error("Shift times must look like 08:00");
      return;
    }

    setBusy(true);
    try {
      const updated = await clientApi<ShopSettings>("/shop-settings", {
        method: "PUT",
        body: JSON.stringify({
          business_name,
          primary_color,
          cashier_shift_start,
          cashier_shift_end,
          waive_first_mechanic_commission,
        }),
      });
      applyLocal(updated);
      toast.success("Shop settings saved");
      await refresh();
    } catch (err) {
      toastError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-xl space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Shop settings</h1>
        <p className="text-sm text-muted-foreground">
          Business name and color for receipts. Cashier shift hours are the
          default schedule — cashiers can still open early or extend when needed.
        </p>
      </div>

      <form
        onSubmit={onSubmit}
        className="space-y-4 rounded-xl border bg-card p-4"
      >
        <div className="space-y-2">
          <Label htmlFor="business-name">Business name</Label>
          <Input
            id="business-name"
            className="min-h-11"
            value={form.business_name}
            onChange={(e) =>
              setForm((prev) => ({ ...prev, business_name: e.target.value }))
            }
            placeholder="e.g. Parreno MotoShop"
            required
            maxLength={120}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="primary-color">Primary color</Label>
          <div className="flex gap-2">
            <Input
              id="primary-color"
              type="color"
              className="h-11 w-14 cursor-pointer p-1"
              value={
                /^#[0-9A-Fa-f]{6}$/.test(form.primary_color)
                  ? form.primary_color
                  : "#C26A1A"
              }
              onChange={(e) =>
                setForm((prev) => ({
                  ...prev,
                  primary_color: e.target.value.toUpperCase(),
                }))
              }
              aria-label="Pick primary color"
            />
            <Input
              className="min-h-11 font-mono uppercase"
              value={form.primary_color}
              onChange={(e) =>
                setForm((prev) => ({
                  ...prev,
                  primary_color: e.target.value.toUpperCase(),
                }))
              }
              placeholder="#C26A1A"
              maxLength={7}
              required
            />
          </div>
          <div className="flex flex-wrap gap-2 pt-1">
            {COLOR_PRESETS.map((preset) => (
              <button
                key={preset.value}
                type="button"
                className="inline-flex min-h-9 items-center gap-2 rounded-lg border px-3 text-xs"
                onClick={() =>
                  setForm((prev) => ({
                    ...prev,
                    primary_color: preset.value,
                  }))
                }
              >
                <span
                  className="size-3 rounded-full border"
                  style={{ backgroundColor: preset.value }}
                />
                {preset.label}
              </button>
            ))}
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="shift-start">Cashier shift start</Label>
            <Input
              id="shift-start"
              type="time"
              className="min-h-11"
              value={form.cashier_shift_start || "08:00"}
              onChange={(e) =>
                setForm((prev) => ({
                  ...prev,
                  cashier_shift_start: e.target.value,
                }))
              }
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="shift-end">Cashier shift end</Label>
            <Input
              id="shift-end"
              type="time"
              className="min-h-11"
              value={form.cashier_shift_end || "17:00"}
              onChange={(e) =>
                setForm((prev) => ({
                  ...prev,
                  cashier_shift_end: e.target.value,
                }))
              }
              required
            />
          </div>
        </div>
        <p className="text-xs text-muted-foreground">
          Default schedule shown on the Shifts screen. Cashiers set their end
          time when opening and can close early or stay extended.
        </p>

        <div className="space-y-2 rounded-xl border p-3">
          <label className="flex items-start gap-3 text-sm">
            <input
              type="checkbox"
              className="mt-1 size-4"
              checked={!!form.waive_first_mechanic_commission}
              onChange={(e) =>
                setForm((prev) => ({
                  ...prev,
                  waive_first_mechanic_commission: e.target.checked,
                }))
              }
            />
            <span>
              <span className="font-medium">
                First mechanic of the day — no commission
              </span>
              <span className="mt-1 block text-xs text-muted-foreground">
                The first mechanic who worked today gets ₱0 commission payout
                (shop keeps full labor). Apply when settling commissions before
                closing the shift.
              </span>
            </span>
          </label>
        </div>

        <div className="rounded-lg border bg-muted/30 p-3">
          <p className="mb-2 text-xs text-muted-foreground">Preview</p>
          <p className="mb-3 font-semibold">
            {form.business_name || "Business name"}
          </p>
          <Button
            type="button"
            className="min-h-11"
            style={{
              backgroundColor: form.primary_color,
              color: "#fff",
            }}
          >
            Sample primary button
          </Button>
        </div>

        <Button type="submit" className="min-h-11 w-full" disabled={busy}>
          {busy ? "Saving…" : "Save settings"}
        </Button>
      </form>
    </div>
  );
}
