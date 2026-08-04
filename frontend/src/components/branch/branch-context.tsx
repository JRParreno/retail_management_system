"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { clientApi, toastError } from "@/lib/client-api";
import type { Branch, User } from "@/lib/types";

const BRANCH_COOKIE = "rms_branch_id";

function readCookie(name: string) {
  if (typeof document === "undefined") return null;
  const match = document.cookie
    .split("; ")
    .find((row) => row.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.split("=")[1] ?? "") : null;
}

function writeCookie(name: string, value: string) {
  document.cookie = `${name}=${encodeURIComponent(value)}; path=/; max-age=31536000; samesite=lax`;
}

type BranchContextValue = {
  user: User | null;
  branches: Branch[];
  activeBranch: Branch | null;
  setActiveBranchId: (id: string) => void;
  refresh: () => Promise<void>;
};

const BranchContext = createContext<BranchContextValue | null>(null);

export function BranchProvider({
  user,
  children,
}: {
  user: User;
  children: ReactNode;
}) {
  const [branches, setBranches] = useState<Branch[]>([]);
  const [activeBranchId, setActiveBranchIdState] = useState<string>(
    user.branch_id,
  );

  const refresh = useCallback(async () => {
    try {
      const list = await clientApi<Branch[]>(
        user.role === "ADMIN"
          ? "/branches?include_inactive=true"
          : "/branches",
      );
      const usable =
        user.role === "ADMIN" ? list : list.filter((b) => b.is_active);
      setBranches(usable);

      const stored = readCookie(BRANCH_COOKIE);
      let next = user.branch_id;
      if (user.role === "ADMIN" && stored && usable.some((b) => b.id === stored)) {
        next = stored;
      } else if (!usable.some((b) => b.id === next) && usable[0]) {
        next = usable[0].id;
      }
      setActiveBranchIdState(next);
      writeCookie(BRANCH_COOKIE, next);
    } catch (err) {
      toastError(err);
    }
  }, [user.branch_id, user.role]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const setActiveBranchId = useCallback(
    (id: string) => {
      if (user.role !== "ADMIN") return;
      setActiveBranchIdState(id);
      writeCookie(BRANCH_COOKIE, id);
      // Reload operational data for the new branch
      window.location.reload();
    },
    [user.role],
  );

  const activeBranch = useMemo(
    () => branches.find((b) => b.id === activeBranchId) ?? null,
    [branches, activeBranchId],
  );

  const value = useMemo(
    () => ({
      user,
      branches,
      activeBranch,
      setActiveBranchId,
      refresh,
    }),
    [user, branches, activeBranch, setActiveBranchId, refresh],
  );

  return (
    <BranchContext.Provider value={value}>{children}</BranchContext.Provider>
  );
}

export function useBranch() {
  const ctx = useContext(BranchContext);
  if (!ctx) {
    throw new Error("useBranch must be used within BranchProvider");
  }
  return ctx;
}
