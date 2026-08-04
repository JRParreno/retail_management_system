"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { clientApi, toastError } from "@/lib/client-api";
import type { Transaction } from "@/lib/types";

export default function NewJobPage() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    customer_name: "",
    customer_phone: "",
    motorcycle_model: "",
    plate_number: "",
    motorcycle_color: "",
    odometer_km: "",
    diagnosis_notes: "",
  });

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const tx = await clientApi<Transaction>("/transactions/service-jobs", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          odometer_km: form.odometer_km ? Number(form.odometer_km) : null,
          motorcycle_color: form.motorcycle_color || null,
          diagnosis_notes: form.diagnosis_notes || null,
        }),
      });
      router.replace(`/jobs/${tx.id}`);
    } catch (err) {
      toastError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-xl space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">New service job</h1>
        <p className="text-sm text-muted-foreground">
          Create an IN PROGRESS job for the bay board
        </p>
      </div>
      <form onSubmit={onSubmit} className="space-y-4 rounded-xl border bg-card p-4">
        {(
          [
            ["plate_number", "Plate number", "e.g. ABC 1234"],
            ["customer_name", "Customer name", "Who owns the bike"],
            ["customer_phone", "Phone number", "09xxxxxxxxx"],
            ["motorcycle_model", "Motorcycle model", "e.g. Honda Click 125"],
            ["motorcycle_color", "Color (optional)", "e.g. Red"],
            ["odometer_km", "Odometer km (optional)", "Current km reading"],
          ] as const
        ).map(([key, label, placeholder]) => (
          <div key={key} className="space-y-2">
            <Label htmlFor={key}>{label}</Label>
            <Input
              id={key}
              className="min-h-11"
              required={!label.includes("optional")}
              placeholder={placeholder}
              value={form[key]}
              onChange={(e) => setForm({ ...form, [key]: e.target.value })}
            />
          </div>
        ))}
        <div className="space-y-2">
          <Label htmlFor="notes">Diagnosis / complaint</Label>
          <Textarea
            id="notes"
            value={form.diagnosis_notes}
            onChange={(e) => setForm({ ...form, diagnosis_notes: e.target.value })}
          />
        </div>
        <Button type="submit" className="min-h-11 w-full" disabled={busy}>
          {busy ? "Creating…" : "Create job"}
        </Button>
      </form>
    </div>
  );
}
