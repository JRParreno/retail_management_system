"use client";

import { useEffect, useRef } from "react";

/**
 * Listens for USB/Bluetooth barcode gun keyboard wedges.
 * Guns typically type characters rapidly then send Enter.
 *
 * On tablets, BT wedges are often slower — use a wider inter-key window.
 * Also allow capture while focused on inputs marked data-barcode-capture.
 */
export function useBarcodeScanner(onScan: (code: string) => void) {
  const buffer = useRef("");
  const lastKeyAt = useRef(0);
  const onScanRef = useRef(onScan);
  onScanRef.current = onScan;

  useEffect(() => {
    function allowsCapture(target: HTMLElement | null) {
      if (!target) return true;
      if (target.closest("[data-barcode-capture='true']")) return true;
      if (
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.isContentEditable
      ) {
        return false;
      }
      return true;
    }

    function onKeyDown(e: KeyboardEvent) {
      const target = e.target as HTMLElement | null;
      if (!allowsCapture(target)) return;

      const now = Date.now();
      // Tablets + BT guns often exceed 50ms between characters
      if (now - lastKeyAt.current > 120) {
        buffer.current = "";
      }
      lastKeyAt.current = now;

      if (e.key === "Enter") {
        const code = buffer.current.trim();
        buffer.current = "";
        if (code.length >= 3) {
          // Avoid double-submit when the focused capture input also handles Enter
          if (target?.closest("[data-barcode-capture='true']")) return;
          onScanRef.current(code);
        }
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
