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

import { clientApi } from "@/lib/client-api";
import type { ShopSettings } from "@/lib/types";

export const DEFAULT_SHOP_SETTINGS: ShopSettings = {
  business_name: "MotoShop RMS",
  primary_color: "#C26A1A",
  cashier_shift_start: "08:00",
  cashier_shift_end: "17:00",
  waive_first_mechanic_commission: false,
};

function contrastForeground(hex: string): string {
  const raw = hex.replace("#", "");
  if (raw.length !== 6) return "#ffffff";
  const r = Number.parseInt(raw.slice(0, 2), 16);
  const g = Number.parseInt(raw.slice(2, 4), 16);
  const b = Number.parseInt(raw.slice(4, 6), 16);
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.55 ? "#1a1208" : "#ffffff";
}

function applyPrimaryColor(hex: string) {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  const fg = contrastForeground(hex);
  root.style.setProperty("--primary", hex);
  root.style.setProperty("--primary-foreground", fg);
  root.style.setProperty("--ring", hex);
  root.style.setProperty("--chart-1", hex);
  root.style.setProperty("--sidebar-primary", hex);
  root.style.setProperty("--sidebar-primary-foreground", fg);
}

type ShopContextValue = {
  settings: ShopSettings;
  loading: boolean;
  refresh: () => Promise<void>;
  applyLocal: (next: ShopSettings) => void;
};

const ShopContext = createContext<ShopContextValue | null>(null);

export function ShopProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<ShopSettings>(DEFAULT_SHOP_SETTINGS);
  const [loading, setLoading] = useState(true);

  const applyLocal = useCallback((next: ShopSettings) => {
    setSettings(next);
    applyPrimaryColor(next.primary_color);
  }, []);

  const refresh = useCallback(async () => {
    try {
      const data = await clientApi<ShopSettings>("/shop-settings");
      applyLocal(data);
    } catch {
      // Login page may load before API is up — keep defaults quietly.
      applyPrimaryColor(DEFAULT_SHOP_SETTINGS.primary_color);
    } finally {
      setLoading(false);
    }
  }, [applyLocal]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const value = useMemo(
    () => ({ settings, loading, refresh, applyLocal }),
    [settings, loading, refresh, applyLocal],
  );

  return <ShopContext.Provider value={value}>{children}</ShopContext.Provider>;
}

export function useShop() {
  const ctx = useContext(ShopContext);
  if (!ctx) {
    throw new Error("useShop must be used within ShopProvider");
  }
  return ctx;
}
