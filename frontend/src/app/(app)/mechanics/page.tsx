"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Plus } from "lucide-react";
import { toast } from "sonner";

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
import type { Mechanic, User } from "@/lib/types";
import { cn } from "@/lib/utils";

export default function MechanicsPage() {
  const [items, setItems] = useState<Mechanic[]>([]);
  const [isAdmin, setIsAdmin] = useState(false);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Mechanic | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    full_name: "",
    nickname: "",
    commission_pct: "15",
    is_active: true,
  });

  const load = useCallback(async () => {
    try {
      const [mechs, me] = await Promise.all([
        clientApi<Mechanic[]>("/mechanics"),
        clientApi<User>("/auth/me"),
      ]);
      setItems(mechs);
      setIsAdmin(me.role === "ADMIN");
    } catch (err) {
      toastError(err);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function openCreate() {
    setEditing(null);
    setForm({
      full_name: "",
      nickname: "",
      commission_pct: "15",
      is_active: true,
    });
    setOpen(true);
  }

  function openEdit(m: Mechanic) {
    setEditing(m);
    setForm({
      full_name: m.full_name,
      nickname: m.nickname,
      commission_pct: String(Number(m.default_commission_rate) * 100),
      is_active: m.is_active,
    });
    setOpen(true);
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const rate = Number(form.commission_pct) / 100;
    if (!Number.isFinite(rate) || rate < 0 || rate > 1) {
      toast.error("Commission must be between 0 and 100%");
      return;
    }
    setBusy(true);
    try {
      const payload = {
        full_name: form.full_name.trim(),
        nickname: form.nickname.trim(),
        default_commission_rate: rate.toFixed(4),
        is_active: form.is_active,
      };
      if (editing) {
        await clientApi(`/mechanics/${editing.id}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
        toast.success("Mechanic updated");
      } else {
        await clientApi("/mechanics", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        toast.success("Mechanic added");
      }
      setOpen(false);
      await load();
    } catch (err) {
      toastError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Mechanics</h1>
          <p className="text-sm text-muted-foreground">
            Commission-only payroll — one mechanic can work multiple open bikes
          </p>
        </div>
        {isAdmin ? (
          <Button className="min-h-11 gap-2" onClick={openCreate}>
            <Plus className="size-4" />
            Add mechanic
          </Button>
        ) : null}
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((m) => (
          <div key={m.id} className="rounded-xl border bg-card p-4">
            <Link href={`/mechanics/${m.id}`} className="block">
              <div className="mb-1 flex items-start justify-between gap-2">
                <p className="text-lg font-semibold hover:underline">
                  {m.nickname}
                </p>
                <Badge variant={m.is_active ? "secondary" : "outline"}>
                  {m.is_active ? "Active" : "Inactive"}
                </Badge>
              </div>
              <p className="text-sm text-muted-foreground">{m.full_name}</p>
              <p className="mt-3 text-sm">
                Default commission:{" "}
                <span className="font-medium">
                  {(Number(m.default_commission_rate) * 100).toFixed(0)}%
                </span>
              </p>
            </Link>
            <div className="mt-3 flex gap-2">
              <Link
                href={`/mechanics/${m.id}`}
                className={cn(buttonVariants({ variant: "secondary" }), "min-h-10 flex-1")}
              >
                View profile
              </Link>
              {isAdmin ? (
                <Button
                  variant="outline"
                  className="min-h-10 flex-1"
                  onClick={() => openEdit(m)}
                >
                  Edit
                </Button>
              ) : null}
            </div>
          </div>
        ))}
        {!items.length ? (
          <p className="text-sm text-muted-foreground">No mechanics yet.</p>
        ) : null}
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>
              {editing ? "Edit mechanic" : "Add mechanic"}
            </DialogTitle>
          </DialogHeader>
          <form onSubmit={onSubmit} className="space-y-3">
            <div className="space-y-2">
              <Label htmlFor="full_name">Full name</Label>
              <Input
                id="full_name"
                className="min-h-11"
                required
                value={form.full_name}
                onChange={(e) => setForm({ ...form, full_name: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="nickname">Nickname</Label>
              <Input
                id="nickname"
                className="min-h-11"
                required
                value={form.nickname}
                onChange={(e) => setForm({ ...form, nickname: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="commission">Commission %</Label>
              <Input
                id="commission"
                className="min-h-11"
                type="number"
                min={0}
                max={100}
                step={1}
                required
                value={form.commission_pct}
                onChange={(e) =>
                  setForm({ ...form, commission_pct: e.target.value })
                }
              />
            </div>
            <label className="flex min-h-11 items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(e) =>
                  setForm({ ...form, is_active: e.target.checked })
                }
              />
              Active
            </label>
            <Button type="submit" className="min-h-11 w-full" disabled={busy}>
              {busy ? "Saving…" : editing ? "Save changes" : "Create mechanic"}
            </Button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
