"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { Bike } from "lucide-react";

import { useShop } from "@/components/shop/shop-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function LoginPage() {
  const router = useRouter();
  const { settings } = useShop();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Login failed");
      }
      router.replace("/dashboard");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-dvh items-center justify-center bg-[radial-gradient(ellipse_at_top,_color-mix(in_oklab,var(--primary)_18%,white),_oklch(0.97_0.01_85)_55%)] p-4">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-md rounded-2xl border bg-card p-6 shadow-sm sm:p-8"
      >
        <div className="mb-6 flex flex-col items-center text-center">
          <div className="mb-3 flex size-14 items-center justify-center rounded-2xl bg-primary text-primary-foreground">
            <Bike className="size-7" />
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">
            {settings.business_name}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Sign in to open the job board and POS
          </p>
        </div>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="username">Username</Label>
            <Input
              id="username"
              autoComplete="username"
              className="min-h-11"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              className="min-h-11"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          {error ? (
            <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </p>
          ) : null}
          <Button type="submit" className="min-h-11 w-full" disabled={loading}>
            {loading ? "Signing in…" : "Sign in"}
          </Button>
        </div>
      </form>
    </div>
  );
}
