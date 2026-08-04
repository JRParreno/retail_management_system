"use client";

import { useEffect, useRef } from "react";

/**
 * Listens for USB/Bluetooth barcode gun keyboard wedges.
 * Guns typically type characters rapidly then send Enter.
 */
export function useBarcodeScanner(onScan: (code: string) => void) {
  const buffer = useRef("");
  const lastKeyAt = useRef(0);
  const onScanRef = useRef(onScan);
  onScanRef.current = onScan;

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      const target = e.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable)
      ) {
        return;
      }

      const now = Date.now();
      if (now - lastKeyAt.current > 50) {
        buffer.current = "";
      }
      lastKeyAt.current = now;

      if (e.key === "Enter") {
        const code = buffer.current.trim();
        buffer.current = "";
        if (code.length >= 3) onScanRef.current(code);
        return;
      }

      if (e.key.length === 1) {
        buffer.current += e.key;
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);
}
