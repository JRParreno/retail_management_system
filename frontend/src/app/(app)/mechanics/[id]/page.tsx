"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowLeft, FileDown } from "lucide-react";

import { useBranch } from "@/components/branch/branch-context";
import { useShop } from "@/components/shop/shop-context";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { clientApi, toastError } from "@/lib/client-api";
import type { MechanicProfile, MechanicProfileLaborLine } from "@/lib/types";
import { formatPeso } from "@/lib/types";
import { cn } from "@/lib/utils";

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function formatRangeLabel(start: string, end: string) {
  const opts: Intl.DateTimeFormatOptions = {
    year: "numeric",
    month: "short",
    day: "numeric",
  };
  const s = new Date(`${start}T00:00:00`).toLocaleDateString("en-PH", opts);
  const e = new Date(`${end}T00:00:00`).toLocaleDateString("en-PH", opts);
  return s === e ? s : `${s} – ${e}`;
}

function motorcycleLabel(line: MechanicProfileLaborLine) {
  const bits = [
    line.plate_number?.trim(),
    line.motorcycle_model?.trim(),
    line.motorcycle_color?.trim(),
  ].filter(Boolean);
  return bits.length ? bits.join(" · ") : "No bike info";
}

export default function MechanicProfilePage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { activeBranch, user } = useBranch();
  const { settings } = useShop();
  const isAdmin = user?.role === "ADMIN";
  const [start, setStart] = useState(todayISO());
  const [end, setEnd] = useState(todayISO());
  const [profile, setProfile] = useState<MechanicProfile | null>(null);
  const [selected, setSelected] = useState<MechanicProfileLaborLine | null>(
    null,
  );

  useEffect(() => {
    if (user && user.role !== "ADMIN") {
      router.replace("/dashboard");
    }
  }, [user, router]);

  async function load(s = start, e = end) {
    try {
      const data = await clientApi<MechanicProfile>(
        `/mechanics/${id}/profile?start_date=${s}&end_date=${e}`,
      );
      setProfile(data);
    } catch (err) {
      toastError(err);
    }
  }

  useEffect(() => {
    if (!isAdmin) return;
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, isAdmin]);

  if (user && !isAdmin) {
    return null;
  }

  function preset(days: number) {
    const endDate = new Date();
    const startDate = new Date();
    startDate.setDate(endDate.getDate() - days + 1);
    const s = startDate.toISOString().slice(0, 10);
    const e = endDate.toISOString().slice(0, 10);
    setStart(s);
    setEnd(e);
    load(s, e);
  }

  function exportPdf() {
    if (!profile) return;
    const previous = document.title;
    document.title = `Mechanic-${profile.nickname}-${start}_to_${end}`;
    window.print();
    document.title = previous;
  }

  if (!profile) {
    return <p className="text-sm text-muted-foreground">Loading profile…</p>;
  }

  const kpis = [
    ["Labor jobs", String(profile.job_count)],
    ["Labor sales", formatPeso(profile.labor_sales)],
    ["Commission earned", formatPeso(profile.commission_total)],
    [
      "Default rate",
      `${(Number(profile.default_commission_rate) * 100).toFixed(0)}%`,
    ],
  ] as const;

  return (
    <div className="space-y-4">
      <div className="no-print flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <Link
            href="/mechanics"
            className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="size-4" /> Mechanics
          </Link>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-tight">
              {profile.nickname}
            </h1>
            <Badge variant={profile.is_active ? "secondary" : "outline"}>
              {profile.is_active ? "Active" : "Inactive"}
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground">{profile.full_name}</p>
        </div>
        <Button
          className="min-h-11 gap-2"
          variant="outline"
          onClick={exportPdf}
        >
          <FileDown className="size-4" />
          Export PDF
        </Button>
      </div>

      <div className="no-print flex flex-wrap gap-2">
        <Button variant="secondary" className="min-h-11" onClick={() => preset(1)}>
          Today
        </Button>
        <Button variant="secondary" className="min-h-11" onClick={() => preset(7)}>
          Week
        </Button>
        <Button variant="secondary" className="min-h-11" onClick={() => preset(30)}>
          Month
        </Button>
      </div>

      <div className="no-print flex flex-col gap-2 sm:flex-row sm:items-end">
        <div className="space-y-2">
          <Label>Start</Label>
          <Input
            type="date"
            className="min-h-11"
            value={start}
            onChange={(e) => setStart(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label>End</Label>
          <Input
            type="date"
            className="min-h-11"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
          />
        </div>
        <Button className="min-h-11" onClick={() => load()}>
          Apply
        </Button>
      </div>

      <div className="report-screen-only grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {kpis.map(([label, value]) => (
          <div key={label} className="rounded-xl border bg-card p-4">
            <p className="text-sm text-muted-foreground">{label}</p>
            <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
          </div>
        ))}
      </div>

      <div className="report-screen-only overflow-x-auto rounded-xl border bg-card">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead className="border-b bg-muted/40">
            <tr>
              <th className="px-3 py-3">Motorcycle</th>
              <th className="px-3 py-3">Service</th>
              <th className="px-3 py-3">Fee</th>
              <th className="px-3 py-3">Payout</th>
              <th className="px-3 py-3">When</th>
            </tr>
          </thead>
          <tbody>
            {profile.recent_lines.map((line) => (
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
                    {[line.motorcycle_model, line.motorcycle_color, line.customer_name]
                      .filter((v) => v && String(v).trim())
                      .join(" · ") || "Tap for details"}
                  </span>
                </td>
                <td className="px-3 py-3 font-medium">{line.service_name}</td>
                <td className="px-3 py-3 tabular-nums">
                  {formatPeso(line.actual_price)}
                </td>
                <td className="px-3 py-3 tabular-nums">
                  {formatPeso(line.mechanic_payout_amount)}
                </td>
                <td className="px-3 py-3 text-muted-foreground">
                  {new Date(line.paid_at ?? line.created_at).toLocaleString(
                    "en-PH",
                  )}
                </td>
              </tr>
            ))}
            {!profile.recent_lines.length ? (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-muted-foreground">
                  No paid labor in this period for the active branch.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      <div className="report-print-area report-print-only">
        <h1>{settings.business_name} — Mechanic Profile</h1>
        <p className="report-print-meta">
          <strong>{profile.nickname}</strong> ({profile.full_name})
          <br />
          Branch: {activeBranch?.name ?? "—"} ({activeBranch?.code ?? "—"})
          <br />
          Period: {formatRangeLabel(start, end)}
          <br />
          Generated: {new Date().toLocaleString("en-PH")}
        </p>
        <table className="report-print-table">
          <thead>
            <tr>
              <th>Metric</th>
              <th>Value</th>
            </tr>
          </thead>
          <tbody>
            {kpis.map(([label, value]) => (
              <tr key={label}>
                <td>{label}</td>
                <td>{value}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <h2 style={{ marginTop: "16pt", fontSize: "14pt" }}>Recent labor</h2>
        <table className="report-print-table">
          <thead>
            <tr>
              <th>Motorcycle</th>
              <th>Service</th>
              <th>Fee</th>
              <th>Payout</th>
            </tr>
          </thead>
          <tbody>
            {profile.recent_lines.map((line) => (
              <tr key={line.id}>
                <td>{motorcycleLabel(line)}</td>
                <td>{line.service_name}</td>
                <td>{formatPeso(line.actual_price)}</td>
                <td>{formatPeso(line.mechanic_payout_amount)}</td>
              </tr>
            ))}
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
                  {[
                    selected.motorcycle_model,
                    selected.motorcycle_color,
                  ]
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
                  <dt className="text-muted-foreground">Labor fee</dt>
                  <dd className="tabular-nums font-medium">
                    {formatPeso(selected.actual_price)}
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Commission rate</dt>
                  <dd className="tabular-nums">
                    {selected.mechanic_commission_rate != null
                      ? `${(Number(selected.mechanic_commission_rate) * 100).toFixed(0)}%`
                      : "—"}
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Payout</dt>
                  <dd className="tabular-nums font-semibold">
                    {formatPeso(selected.mechanic_payout_amount)}
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Paid</dt>
                  <dd>
                    {new Date(
                      selected.paid_at ?? selected.created_at,
                    ).toLocaleString("en-PH")}
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
