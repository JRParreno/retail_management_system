"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { clientApi, toastError } from "@/lib/client-api";
import type { Branch } from "@/lib/types";

export default function BranchesPage() {
  const [items, setItems] = useState<Branch[]>([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Branch | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    code: "",
    name: "",
    address: "",
    phone: "",
    is_active: true,
  });

  const load = useCallback(async () => {
    try {
      setItems(await clientApi<Branch[]>("/branches?include_inactive=true"));
    } catch (err) {
      toastError(err);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function openCreate() {
    setEditing(null);
    setForm({ code: "", name: "", address: "", phone: "", is_active: true });
    setOpen(true);
  }

  function openEdit(branch: Branch) {
    setEditing(branch);
    setForm({
      code: branch.code,
      name: branch.name,
      address: branch.address ?? "",
      phone: branch.phone ?? "",
      is_active: branch.is_active,
    });
    setOpen(true);
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      if (editing) {
        await clientApi(`/branches/${editing.id}`, {
          method: "PATCH",
          body: JSON.stringify({
            name: form.name.trim(),
            address: form.address.trim() || null,
            phone: form.phone.trim() || null,
            is_active: form.is_active,
          }),
        });
        toast.success("Branch updated");
      } else {
        await clientApi("/branches", {
          method: "POST",
          body: JSON.stringify({
            code: form.code.trim().toUpperCase(),
            name: form.name.trim(),
            address: form.address.trim() || null,
            phone: form.phone.trim() || null,
            is_active: form.is_active,
          }),
        });
        toast.success("Branch created");
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
          <h1 className="text-2xl font-semibold tracking-tight">Branches</h1>
          <p className="text-sm text-muted-foreground">
            Manage shop locations — stock, docs, and prices are per branch
          </p>
        </div>
        <Button className="min-h-11 gap-2" onClick={openCreate}>
          <Plus className="size-4" />
          Add branch
        </Button>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((b) => (
          <div key={b.id} className="rounded-xl border bg-card p-4">
            <div className="mb-1 flex items-start justify-between gap-2">
              <div>
                <p className="text-lg font-semibold">{b.name}</p>
                <p className="text-xs text-muted-foreground">Code {b.code}</p>
              </div>
              <Badge variant={b.is_active ? "secondary" : "outline"}>
                {b.is_active ? "Active" : "Inactive"}
              </Badge>
            </div>
            {b.address ? (
              <p className="mt-2 text-sm text-muted-foreground">{b.address}</p>
            ) : null}
            {b.phone ? <p className="text-sm">{b.phone}</p> : null}
            <Button
              variant="outline"
              className="mt-3 min-h-10 w-full"
              onClick={() => openEdit(b)}
            >
              Edit
            </Button>
          </div>
        ))}
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{editing ? "Edit branch" : "Add branch"}</DialogTitle>
          </DialogHeader>
          <form onSubmit={onSubmit} className="space-y-3">
            {!editing ? (
              <div className="space-y-2">
                <Label htmlFor="code">Code</Label>
                <Input
                  id="code"
                  className="min-h-11 uppercase"
                  required
                  maxLength={16}
                  placeholder="e.g. NORTH"
                  value={form.code}
                  onChange={(e) => setForm({ ...form, code: e.target.value })}
                />
              </div>
            ) : null}
            <div className="space-y-2">
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                className="min-h-11"
                required
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="address">Address (optional)</Label>
              <Input
                id="address"
                className="min-h-11"
                value={form.address}
                onChange={(e) => setForm({ ...form, address: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="phone">Phone (optional)</Label>
              <Input
                id="phone"
                className="min-h-11"
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
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
              {busy ? "Saving…" : editing ? "Save changes" : "Create branch"}
            </Button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
