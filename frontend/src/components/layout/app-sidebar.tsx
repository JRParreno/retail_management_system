"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  ArrowLeftRight,
  Bike,
  Building2,
  ClipboardList,
  Clock3,
  LayoutDashboard,
  LogOut,
  Menu,
  Package,
  Receipt,
  RotateCcw,
  ShoppingCart,
  Users,
  Wrench,
} from "lucide-react";
import { useState } from "react";

import { useBranch } from "@/components/branch/branch-context";
import { Button } from "@/components/ui/button";
import { SearchableCombobox } from "@/components/ui/searchable-combobox";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import type { Role, User } from "@/lib/types";
import { cn } from "@/lib/utils";

const NAV: { href: string; label: string; icon: typeof Bike; roles?: Role[] }[] =
  [
    { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
    { href: "/jobs", label: "Job Board", icon: ClipboardList },
    { href: "/pos", label: "Direct Sale", icon: ShoppingCart },
    { href: "/refunds", label: "Refunds", icon: RotateCcw },
    { href: "/inventory", label: "Inventory", icon: Package },
    { href: "/transfers", label: "Transfers", icon: ArrowLeftRight, roles: ["ADMIN"] },
    { href: "/mechanics", label: "Mechanics", icon: Wrench },
    { href: "/shifts", label: "Shifts", icon: Clock3 },
    { href: "/reports", label: "Reports", icon: Receipt },
    { href: "/branches", label: "Branches", icon: Building2, roles: ["ADMIN"] },
    { href: "/users", label: "Users", icon: Users, roles: ["ADMIN"] },
  ];

function NavLinks({
  user,
  onNavigate,
}: {
  user: User;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  return (
    <nav className="flex flex-col gap-1 p-3">
      {NAV.filter((item) => !item.roles || item.roles.includes(user.role)).map(
        (item) => {
          const Icon = item.icon;
          const active =
            pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
              className={cn(
                "flex min-h-11 items-center gap-3 rounded-lg px-3 text-sm font-medium transition-colors",
                active
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-sidebar-foreground/80 hover:bg-sidebar-accent/70 hover:text-sidebar-accent-foreground",
              )}
            >
              <Icon className="size-5 shrink-0" />
              {item.label}
            </Link>
          );
        },
      )}
    </nav>
  );
}

function BranchControl() {
  const { user, branches, activeBranch, setActiveBranchId } = useBranch();
  if (!activeBranch) return null;

  if (user?.role !== "ADMIN") {
    return (
      <p className="px-2 text-xs text-sidebar-foreground/60">
        Branch: {activeBranch.name}
      </p>
    );
  }

  return (
    <div className="min-w-0 space-y-1 px-1">
      <p className="px-2 text-xs text-sidebar-foreground/50">Active branch</p>
      <SearchableCombobox
        className="w-full min-w-0 bg-sidebar-accent/40 text-sidebar-foreground"
        value={activeBranch.id}
        onValueChange={setActiveBranchId}
        placeholder="Select branch"
        searchPlaceholder="Search branch…"
        options={branches.map((b) => ({
          value: b.id,
          label: `${b.name} (${b.code})`,
          description: b.is_active ? undefined : "Inactive",
        }))}
      />
    </div>
  );
}

function SidebarChrome({
  user,
  onNavigate,
}: {
  user: User;
  onNavigate?: () => void;
}) {
  const router = useRouter();

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.replace("/login");
    router.refresh();
  }

  return (
    <>
      <div className="shrink-0 border-b border-sidebar-border px-4 py-4">
        <div className="flex min-w-0 items-center gap-2">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
            <Bike className="size-5" />
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold tracking-tight text-sidebar-foreground">
              MotoShop RMS
            </p>
            <p className="truncate text-xs text-sidebar-foreground/60">
              {user.full_name}
            </p>
          </div>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
        <NavLinks user={user} onNavigate={onNavigate} />
      </div>

      <div className="shrink-0 space-y-3 border-t border-sidebar-border p-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
        <BranchControl />
        <p className="truncate px-2 text-xs text-sidebar-foreground/50">
          {user.role} · @{user.username}
        </p>
        <Button
          variant="secondary"
          className="h-11 w-full min-w-0 justify-start gap-2 px-3"
          onClick={logout}
        >
          <LogOut className="size-4 shrink-0" />
          <span className="truncate">Sign out</span>
        </Button>
      </div>
    </>
  );
}

export function AppSidebar({ user }: { user: User }) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <aside className="no-print hidden h-dvh w-60 shrink-0 flex-col overflow-hidden bg-sidebar text-sidebar-foreground lg:flex">
        <SidebarChrome user={user} />
      </aside>

      <div className="no-print sticky top-0 z-40 flex items-center gap-3 border-b bg-card/90 px-3 py-2 backdrop-blur lg:hidden">
        <Sheet open={open} onOpenChange={setOpen}>
          <SheetTrigger
            className={cn(
              "inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg border border-border bg-background",
            )}
          >
            <Menu className="size-5" />
          </SheetTrigger>
          <SheetContent
            side="left"
            className="flex h-dvh w-72 max-w-[85vw] flex-col gap-0 overflow-hidden bg-sidebar p-0 text-sidebar-foreground"
          >
            <SidebarChrome
              user={user}
              onNavigate={() => setOpen(false)}
            />
          </SheetContent>
        </Sheet>
        <div className="flex min-w-0 flex-1 items-center gap-2">
          <Bike className="size-5 shrink-0 text-primary" />
          <span className="truncate font-semibold">MotoShop RMS</span>
        </div>
      </div>
    </>
  );
}
