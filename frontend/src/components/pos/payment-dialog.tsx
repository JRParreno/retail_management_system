"use client";

import { useEffect, useRef, useState } from "react";
import { Camera, Check } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { clientApi, toastError } from "@/lib/client-api";
import type { PaymentMethod } from "@/lib/types";
import { formatPeso } from "@/lib/types";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  balanceDue: number;
  /** When true, cashier can pay less than the full balance (service jobs). */
  allowPartial?: boolean;
  onPaid: (payment: {
    payment_method: PaymentMethod;
    amount: string;
    amount_tendered?: string;
    change_due?: string;
    reference_no?: string;
    proof_image_url?: string;
  }) => Promise<void> | void;
};

function roundMoney(value: number) {
  return Math.round((value + Number.EPSILON) * 100) / 100;
}

export function PaymentDialog({
  open,
  onOpenChange,
  balanceDue,
  allowPartial = false,
  onPaid,
}: Props) {
  const [method, setMethod] = useState<PaymentMethod>("CASH");
  const [payAmount, setPayAmount] = useState("");
  const [tendered, setTendered] = useState("");
  const [reference, setReference] = useState("");
  const [proofUrl, setProofUrl] = useState<string | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [cameraOn, setCameraOn] = useState(false);

  const balance = roundMoney(Math.max(0, balanceDue));

  useEffect(() => {
    if (!open) {
      stopCamera();
      setMethod("CASH");
      setPayAmount("");
      setTendered("");
      setReference("");
      setProofUrl(null);
      setPreview(null);
      return;
    }
    setPayAmount(balance > 0 ? balance.toFixed(2) : "");
  }, [open, balance]);

  function stopCamera() {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setCameraOn(false);
  }

  async function startCamera() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" } },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setCameraOn(true);
    } catch (err) {
      toastError(err);
    }
  }

  async function captureProof() {
    const video = videoRef.current;
    if (!video) return;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth || 1280;
    canvas.height = video.videoHeight || 720;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(video, 0, 0);
    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/jpeg", 0.85),
    );
    if (!blob) return;
    setPreview(URL.createObjectURL(blob));
    const form = new FormData();
    form.append("file", blob, "gcash-proof.jpg");
    try {
      const res = await clientApi<{ url: string }>("/uploads/payment-proof", {
        method: "POST",
        body: form,
      });
      setProofUrl(res.url);
      stopCamera();
    } catch (err) {
      toastError(err);
    }
  }

  const payNum = roundMoney(Number(payAmount || 0));
  const chargeAmount = allowPartial ? payNum : balance;
  const tenderNum = Number(tendered || 0);
  const change =
    method === "CASH" ? Math.max(0, roundMoney(tenderNum - chargeAmount)) : 0;

  const amountValid =
    chargeAmount > 0 && (!allowPartial || chargeAmount <= balance + 0.001);

  const canPay =
    amountValid &&
    (method === "CASH"
      ? tenderNum >= chargeAmount
      : Boolean(reference.trim() && proofUrl));

  const isPartial =
    allowPartial && chargeAmount > 0 && chargeAmount < balance - 0.001;

  async function submit() {
    if (!canPay) return;
    setBusy(true);
    try {
      await onPaid({
        payment_method: method,
        amount: chargeAmount.toFixed(2),
        ...(method === "CASH"
          ? {
              amount_tendered: tenderNum.toFixed(2),
              change_due: change.toFixed(2),
            }
          : {
              reference_no: reference.trim(),
              proof_image_url: proofUrl!,
            }),
      });
      onOpenChange(false);
    } catch (err) {
      toastError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            Collect payment · balance {formatPeso(balance)}
          </DialogTitle>
          <DialogDescription>
            {allowPartial
              ? "You can take a partial payment now. Enter any amount up to the balance — the job stays open until the remaining balance is paid in full."
              : "Enter cash tendered or GCash details to complete this payment in full."}
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-2 gap-2">
          {(["CASH", "GCASH"] as PaymentMethod[]).map((m) => (
            <Button
              key={m}
              type="button"
              variant={method === m ? "default" : "outline"}
              className="min-h-12"
              onClick={() => {
                setMethod(m);
                stopCamera();
              }}
            >
              {m}
            </Button>
          ))}
        </div>

        {allowPartial ? (
          <div className="space-y-2">
            <Label>Amount to collect</Label>
            <Input
              className="min-h-11 text-lg"
              inputMode="decimal"
              value={payAmount}
              onChange={(e) => setPayAmount(e.target.value)}
              placeholder="0.00"
            />
            <p className="text-xs text-muted-foreground">
              Tip: use <span className="font-medium text-foreground">Full</span>{" "}
              to settle now, or{" "}
              <span className="font-medium text-foreground">Half</span> / a custom
              amount for a deposit or partial.
            </p>
            <div className="grid grid-cols-3 gap-2">
              {[
                { label: "Full", value: balance },
                { label: "Half", value: roundMoney(balance / 2) },
                {
                  label: "Custom",
                  value: null as number | null,
                },
              ].map((item) =>
                item.value == null ? (
                  <Button
                    key={item.label}
                    type="button"
                    variant="secondary"
                    className="min-h-11"
                    onClick={() => setPayAmount("")}
                  >
                    Clear
                  </Button>
                ) : (
                  <Button
                    key={item.label}
                    type="button"
                    variant="secondary"
                    className="min-h-11"
                    onClick={() => setPayAmount(item.value!.toFixed(2))}
                  >
                    {item.label}
                  </Button>
                ),
              )}
            </div>
            {isPartial ? (
              <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-950 dark:text-amber-100">
                Partial payment of {formatPeso(chargeAmount)}. Remaining after
                this: {formatPeso(roundMoney(balance - chargeAmount))}.
              </p>
            ) : chargeAmount > 0 ? (
              <p className="text-xs text-muted-foreground">
                This will settle the full balance.
              </p>
            ) : null}
          </div>
        ) : null}

        {method === "CASH" ? (
          <div className="space-y-3">
            <div className="space-y-2">
              <Label>Amount tendered</Label>
              <Input
                className="min-h-11 text-lg"
                inputMode="decimal"
                value={tendered}
                onChange={(e) => setTendered(e.target.value)}
                placeholder="0.00"
              />
            </div>
            <p className="text-sm text-muted-foreground">
              Change:{" "}
              <span className="font-semibold text-foreground">
                {formatPeso(change)}
              </span>
            </p>
            <div className="grid grid-cols-3 gap-2">
              {[chargeAmount || balance, 500, 1000].map((amt) => (
                <Button
                  key={amt}
                  type="button"
                  variant="secondary"
                  className="min-h-11"
                  onClick={() => setTendered(String(amt))}
                >
                  {formatPeso(amt)}
                </Button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="space-y-2">
              <Label>GCash reference no.</Label>
              <Input
                className="min-h-11"
                value={reference}
                onChange={(e) => setReference(e.target.value)}
                placeholder="Enter GCash txn / ref"
              />
            </div>
            <div className="space-y-2">
              <Label>Proof photo (required)</Label>
              {preview || proofUrl ? (
                <div className="space-y-2">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={
                      preview ||
                      `${process.env.NEXT_PUBLIC_BACKEND_URL}${proofUrl}`
                    }
                    alt="GCash proof"
                    className="max-h-48 w-full rounded-lg border object-contain"
                  />
                  <div className="flex items-center gap-2 text-sm text-primary">
                    <Check className="size-4" /> Proof captured
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    className="min-h-11 w-full"
                    onClick={() => {
                      setPreview(null);
                      setProofUrl(null);
                      startCamera();
                    }}
                  >
                    Retake
                  </Button>
                </div>
              ) : cameraOn ? (
                <div className="space-y-2">
                  <video
                    ref={videoRef}
                    className="aspect-video w-full rounded-lg bg-black object-cover"
                    playsInline
                    muted
                  />
                  <Button
                    type="button"
                    className="min-h-11 w-full"
                    onClick={captureProof}
                  >
                    <Camera className="mr-2 size-4" /> Capture proof
                  </Button>
                </div>
              ) : (
                <Button
                  type="button"
                  variant="secondary"
                  className="min-h-11 w-full"
                  onClick={startCamera}
                >
                  <Camera className="mr-2 size-4" /> Open camera
                </Button>
              )}
            </div>
          </div>
        )}

        <Button
          type="button"
          className="min-h-12 w-full text-base"
          disabled={!canPay || busy}
          onClick={submit}
        >
          {busy
            ? "Processing…"
            : isPartial
              ? `Confirm partial · ${formatPeso(chargeAmount)}`
              : `Confirm payment · ${formatPeso(chargeAmount)}`}
        </Button>
      </DialogContent>
    </Dialog>
  );
}
