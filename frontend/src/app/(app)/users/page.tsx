"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
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
import { SearchableCombobox } from "@/components/ui/searchable-combobox";
import { clientApi, ClientApiError, toastError } from "@/lib/client-api";
import type { Branch, Role, User } from "@/lib/types";

export default function UsersPage() {
  const router = useRouter();
  const [users, setUsers] = useState<User[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<User | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    username: "",
    password: "",
    full_name: "",
    role: "CASHIER" as Role,
    branch_id: "",
    is_active: true,
  });

  const load = useCallback(async () => {
    try {
      const [list, branchList] = await Promise.all([
        clientApi<User[]>("/users"),
        clientApi<Branch[]>("/branches?include_inactive=true"),
      ]);
      setUsers(list);
      setBranches(branchList);
    } catch (err) {
      toastError(err);
      if (err instanceof ClientApiError && err.status === 403) {
        router.replace("/dashboard");
      }
    }
  }, [router]);

  useEffect(() => {
    load();
  }, [load]);

  function branchLabel(id: string) {
    const b = branches.find((x) => x.id === id);
    return b ? `${b.name} (${b.code})` : "—";
  }

  function openCreate() {
    setEditing(null);
    setForm({
      username: "",
      password: "",
      full_name: "",
      role: "CASHIER",
      branch_id: branches[0]?.id ?? "",
      is_active: true,
    });
    setOpen(true);
  }

  function openEdit(user: User) {
    setEditing(user);
    setForm({
      username: user.username,
      password: "",
      full_name: user.full_name,
      role: user.role,
      branch_id: user.branch_id,
      is_active: user.is_active,
    });
    setOpen(true);
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!form.branch_id) {
      toast.error("Select a branch");
      return;
    }
    setBusy(true);
    try {
      if (editing) {
        const body: Record<string, unknown> = {
          full_name: form.full_name.trim(),
          role: form.role,
          branch_id: form.branch_id,
          is_active: form.is_active,
        };
        if (form.password.trim()) {
          body.password = form.password;
        }
        await clientApi(`/users/${editing.id}`, {
          method: "PATCH",
          body: JSON.stringify(body),
        });
        toast.success("User updated");
      } else {
        await clientApi("/users", {
          method: "POST",
          body: JSON.stringify({
            username: form.username.trim(),
            password: form.password,
            full_name: form.full_name.trim(),
            role: form.role,
            branch_id: form.branch_id,
            is_active: form.is_active,
          }),
        });
        toast.success(
          form.role === "ADMIN"
            ? "Admin account created"
            : "Cashier account created",
        );
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
          <h1 className="text-2xl font-semibold tracking-tight">Users</h1>
          <p className="text-sm text-muted-foreground">
            Assign each cashier to a home branch
          </p>
        </div>
        <Button className="min-h-11 gap-2" onClick={openCreate}>
          <Plus className="size-4" />
          Add user
        </Button>
      </div>

      <div className="overflow-x-auto rounded-xl border bg-card">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="border-b bg-muted/40">
            <tr>
              <th className="px-3 py-3">Name</th>
              <th className="px-3 py-3">Username</th>
              <th className="px-3 py-3">Role</th>
              <th className="px-3 py-3">Branch</th>
              <th className="px-3 py-3">Status</th>
              <th className="px-3 py-3" />
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-b last:border-0">
                <td className="px-3 py-3 font-medium">{u.full_name}</td>
                <td className="px-3 py-3">{u.username}</td>
                <td className="px-3 py-3">
                  <Badge variant="secondary">{u.role}</Badge>
                </td>
                <td className="px-3 py-3">{branchLabel(u.branch_id)}</td>
                <td className="px-3 py-3">
                  {u.is_active ? "Active" : "Inactive"}
                </td>
                <td className="px-3 py-3 text-right">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => openEdit(u)}
                  >
                    Edit
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{editing ? "Edit user" : "Add user"}</DialogTitle>
          </DialogHeader>
          <form onSubmit={onSubmit} className="space-y-3">
            <div className="space-y-2">
              <Label htmlFor="full_name">Full name</Label>
              <Input
                id="full_name"
                className="min-h-11"
                required
                value={form.full_name}
                onChange={(e) =>
                  setForm({ ...form, full_name: e.target.value })
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="username">Username</Label>
              <Input
                id="username"
                className="min-h-11"
                required={!editing}
                disabled={Boolean(editing)}
                minLength={3}
                value={form.username}
                onChange={(e) => setForm({ ...form, username: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">
                Password{editing ? " (leave blank to keep)" : ""}
              </Label>
              <Input
                id="password"
                type="password"
                className="min-h-11"
                required={!editing}
                minLength={6}
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>Role</Label>
              <SearchableCombobox
                value={form.role}
                onValueChange={(v) => setForm({ ...form, role: v as Role })}
                placeholder="Select role"
                options={[
                  {
                    value: "CASHIER",
                    label: "CASHIER",
                    description: "Locked to assigned branch",
                  },
                  {
                    value: "ADMIN",
                    label: "ADMIN",
                    description: "Can switch branches",
                  },
                ]}
              />
            </div>
            <div className="space-y-2">
              <Label>Home branch</Label>
              <SearchableCombobox
                value={form.branch_id}
                onValueChange={(v) => setForm({ ...form, branch_id: v })}
                placeholder="Select branch"
                options={branches.map((b) => ({
                  value: b.id,
                  label: `${b.name} (${b.code})`,
                }))}
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
              {busy ? "Saving…" : editing ? "Save changes" : "Create user"}
            </Button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
