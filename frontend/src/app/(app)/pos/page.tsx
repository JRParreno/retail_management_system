"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Minus, Plus, ScanBarcode, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { BarcodeScanModal } from "@/components/pos/barcode-scan-modal";
import { PaymentDialog } from "@/components/pos/payment-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { clientApi, toastError } from "@/lib/client-api";
import type { Paginated, Product } from "@/lib/types";
import { formatPeso } from "@/lib/types";
import { useBarcodeScanner } from "@/hooks/use-barcode-scanner";

type CartLine = { product: Product; quantity: number };

export default function PosPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [q, setQ] = useState("");
  const [barcodeQuery, setBarcodeQuery] = useState("");
  const [scanOpen, setScanOpen] = useState(false);
  const [cart, setCart] = useState<CartLine[]>([]);
  const [payOpen, setPayOpen] = useState(false);

  useEffect(() => {
    clientApi<Paginated<Product>>("/products?page_size=100")
      .then((res) => setProducts(res.items))
      .catch(toastError);
  }, []);

  const addToCart = useCallback((product: Product, opts?: { quiet?: boolean }) => {
    setCart((prev) => {
      const existing = prev.find((l) => l.product.id === product.id);
      if (existing) {
        if (existing.quantity >= product.stock_qty) return prev;
        return prev.map((l) =>
          l.product.id === product.id
            ? { ...l, quantity: l.quantity + 1 }
            : l,
        );
      }
      if (product.stock_qty < 1) return prev;
      return [...prev, { product, quantity: 1 }];
    });
    if (!opts?.quiet) {
      toast.success(`Added ${product.name}`);
    }
  }, []);

  const setCartQuantity = useCallback((productId: string, next: number) => {
    setCart((prev) =>
      prev.map((line) => {
        if (line.product.id !== productId) return line;
        const quantity = Math.min(
          line.product.stock_qty,
          Math.max(1, Math.floor(next || 1)),
        );
        return { ...line, quantity };
      }),
    );
  }, []);

  const resolveBarcode = useCallback(
    async (code: string) => {
      const trimmed = code.trim();
      if (!trimmed) return;

      let product =
        products.find(
          (p) => p.barcode.toLowerCase() === trimmed.toLowerCase(),
        ) ?? null;

      if (!product) {
        try {
          const res = await clientApi<Paginated<Product>>(
            `/products?q=${encodeURIComponent(trimmed)}&page_size=20`,
          );
          product =
            res.items.find(
              (p) => p.barcode.toLowerCase() === trimmed.toLowerCase(),
            ) ??
            res.items[0] ??
            null;
          if (res.items.length) {
            setProducts((prev) => {
              const map = new Map(prev.map((p) => [p.id, p]));
              for (const item of res.items) map.set(item.id, item);
              return Array.from(map.values());
            });
          }
        } catch (err) {
          toastError(err);
          return;
        }
      }

      if (!product) {
        toast.error(`No product found for barcode “${trimmed}”`);
        return;
      }

      setBarcodeQuery(product.barcode);
      addToCart(product);
    },
    [products, addToCart],
  );

  useBarcodeScanner((code) => {
    if (payOpen || scanOpen) return;
    void resolveBarcode(code);
  });

  const filtered = useMemo(() => {
    const term = q.trim().toLowerCase();
    if (!term) return products;
    return products.filter(
      (p) =>
        p.name.toLowerCase().includes(term) ||
        p.barcode.toLowerCase().includes(term) ||
        (p.brand?.toLowerCase().includes(term) ?? false),
    );
  }, [products, q]);

  const total = cart.reduce(
    (sum, line) =>
      sum + Number(line.product.current_selling_price) * line.quantity,
    0,
  );

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Direct sale</h1>
        <p className="text-sm text-muted-foreground">
          Counter checkout — barcode gun, camera scan, or tap products
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <section className="space-y-3">
          <div className="space-y-2">
            <Label>Barcode / SKU</Label>
            <div className="flex gap-2">
              <Input
                className="min-h-11 font-mono"
                data-barcode-capture="true"
                autoComplete="off"
                placeholder="Scan or type barcode, then Enter"
                value={barcodeQuery}
                onChange={(e) => setBarcodeQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    void resolveBarcode(barcodeQuery);
                  }
                }}
              />
              <Button
                type="button"
                variant="outline"
                className="min-h-11 min-w-11"
                onClick={() => setScanOpen(true)}
                title="Open camera scanner"
              >
                <ScanBarcode className="size-5" />
              </Button>
            </div>
          </div>

          <div className="relative">
            <Input
              className="min-h-11"
              placeholder="Search name, brand, or barcode"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>

          <div className="grid max-h-[60dvh] gap-2 overflow-auto sm:grid-cols-2">
            {filtered.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => addToCart(p, { quiet: true })}
                className="rounded-xl border bg-card p-3 text-left transition-colors hover:border-primary/50"
              >
                <p className="font-medium">{p.name}</p>
                <p className="text-xs text-muted-foreground">
                  {p.brand ? `${p.brand} · ` : ""}
                  {p.barcode}
                </p>
                <div className="mt-2 flex justify-between text-sm">
                  <span>{formatPeso(p.current_selling_price)}</span>
                  <span className="text-muted-foreground">
                    Stock {p.stock_qty}
                  </span>
                </div>
              </button>
            ))}
          </div>
        </section>

        <section className="rounded-xl border bg-card p-4 lg:sticky lg:top-4 lg:self-start">
          <h2 className="mb-3 font-semibold">Cart</h2>
          <ul className="mb-4 max-h-[40dvh] space-y-2 overflow-auto text-sm">
            {cart.map((line) => (
              <li
                key={line.product.id}
                className="space-y-2 rounded-lg border p-3"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="truncate font-medium">{line.product.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {formatPeso(line.product.current_selling_price)} each ·
                      stock {line.product.stock_qty}
                    </p>
                  </div>
                  <p className="shrink-0 tabular-nums font-medium">
                    {formatPeso(
                      Number(line.product.current_selling_price) *
                        line.quantity,
                    )}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    className="size-9"
                    aria-label={`Decrease ${line.product.name} quantity`}
                    onClick={() =>
                      setCartQuantity(
                        line.product.id,
                        line.quantity - 1,
                      )
                    }
                    disabled={line.quantity <= 1}
                  >
                    <Minus className="size-4" />
                  </Button>
                  <Input
                    className="h-9 w-20 text-center tabular-nums"
                    type="number"
                    inputMode="numeric"
                    min={1}
                    max={line.product.stock_qty}
                    value={line.quantity}
                    aria-label={`${line.product.name} quantity`}
                    onChange={(e) =>
                      setCartQuantity(
                        line.product.id,
                        Number(e.target.value),
                      )
                    }
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    className="size-9"
                    aria-label={`Increase ${line.product.name} quantity`}
                    onClick={() =>
                      setCartQuantity(
                        line.product.id,
                        line.quantity + 1,
                      )
                    }
                    disabled={line.quantity >= line.product.stock_qty}
                  >
                    <Plus className="size-4" />
                  </Button>
                  <span className="text-xs text-muted-foreground">Qty</span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="ml-auto size-9"
                    aria-label={`Remove ${line.product.name}`}
                    onClick={() =>
                      setCart((prev) =>
                        prev.filter(
                          (l) => l.product.id !== line.product.id,
                        ),
                      )
                    }
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </div>
              </li>
            ))}
            {!cart.length ? (
              <li className="text-muted-foreground">Cart is empty</li>
            ) : null}
          </ul>
          <p className="mb-3 text-xl font-semibold tabular-nums">
            {formatPeso(total)}
          </p>
          <Button
            className="min-h-12 w-full text-base"
            disabled={!cart.length}
            onClick={() => setPayOpen(true)}
          >
            Checkout
          </Button>
        </section>
      </div>

      <BarcodeScanModal
        open={scanOpen}
        onOpenChange={setScanOpen}
        onScan={(code) => {
          void resolveBarcode(code);
        }}
      />

      <PaymentDialog
        open={payOpen}
        onOpenChange={setPayOpen}
        balanceDue={total}
        onPaid={async (payment) => {
          await clientApi("/transactions/direct-sales", {
            method: "POST",
            body: JSON.stringify({
              part_lines: cart.map((line) => ({
                product_id: line.product.id,
                quantity: line.quantity,
              })),
              payment,
            }),
          });
          setCart([]);
          setQ("");
          setBarcodeQuery("");
        }}
      />
    </div>
  );
}
