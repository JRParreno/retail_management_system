import { toast } from "sonner";

import type { Mechanic, Product, Transaction } from "@/lib/types";
import { formatPeso } from "@/lib/types";

export type JobPrintVariant = "estimate" | "completion";

function esc(value: string) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function money(value: string | number | null | undefined) {
  return esc(formatPeso(value));
}

type PrintJobDocumentArgs = {
  tx: Transaction;
  products: Product[];
  mechanics: Mechanic[];
  variant?: JobPrintVariant;
  businessName?: string;
  primaryColor?: string;
};

function variantCopy(variant: JobPrintVariant) {
  if (variant === "completion") {
    return {
      titleSuffix: "Job complete",
      subtitle: "Completed service job",
      banner: "JOB COMPLETE",
      footer:
        "Work completed. Collect remaining balance if any.<br/>Not a BIR official receipt.",
      docTitle: "Job complete",
    };
  }
  return {
    titleSuffix: "Estimate",
    subtitle: "Parts & labor estimate",
    banner: "SERVICE ESTIMATE",
    footer:
      "Estimate only — amounts may change after inspection or approval.<br/>Not a final official receipt.",
    docTitle: "Estimate",
  };
}

function buildJobDocumentHtml({
  tx,
  products,
  mechanics,
  variant = "estimate",
  businessName = "MotoShop RMS",
  primaryColor = "#C26A1A",
}: PrintJobDocumentArgs) {
  const copy = variantCopy(variant);
  const productById = new Map(products.map((p) => [p.id, p]));
  const mechanicById = new Map(mechanics.map((m) => [m.id, m]));
  const printedAt = new Date().toLocaleString();

  const partRows = tx.part_lines.length
    ? tx.part_lines
        .map((line) => {
          const product = productById.get(line.product_id);
          const name = esc(product?.name ?? "Product");
          const barcode = product?.barcode ? esc(product.barcode) : "";
          const qty = line.quantity;
          const lineTotal = Number(line.actual_selling_price) * line.quantity;
          return `<tr>
            <td>
              <div class="item">${name}</div>
              ${barcode ? `<div class="meta">${barcode}</div>` : ""}
              <div class="meta">x ${qty} @ ${money(line.actual_selling_price)}</div>
            </td>
            <td class="amt">${money(lineTotal)}</td>
          </tr>`;
        })
        .join("")
    : `<tr><td colspan="2" class="empty">No parts</td></tr>`;

  const laborRows = tx.labor_lines.length
    ? tx.labor_lines
        .map((line) => {
          const mech = line.mechanic_id
            ? mechanicById.get(line.mechanic_id)
            : null;
          const name = esc(line.service_name);
          const info = [mech?.nickname, line.description?.trim() || null]
            .filter(Boolean)
            .map((v) => esc(String(v)))
            .join(" · ");
          return `<tr>
            <td>
              <div class="item">${name}</div>
              ${info ? `<div class="meta">${info}</div>` : ""}
            </td>
            <td class="amt">${money(line.actual_price)}</td>
          </tr>`;
        })
        .join("")
    : `<tr><td colspan="2" class="empty">No labor / service</td></tr>`;

  const customerBits = [
    tx.customer_name,
    tx.customer_phone,
    tx.motorcycle_model,
    tx.plate_number,
    tx.motorcycle_color,
    tx.odometer_km != null ? `${tx.odometer_km} km` : null,
  ]
    .filter((v) => v != null && String(v).trim())
    .map((v) => esc(String(v)));

  const paid = Number(tx.totals?.paid_total ?? 0);
  const showPaymentRows = variant === "completion" || paid > 0;

  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>${esc(copy.docTitle)} ${esc(tx.document_number)}</title>
  <style>
    * { box-sizing: border-box; }
    body {
      margin: 0;
      padding: 8mm;
      font-family: system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
      color: #000;
      background: #fff;
      font-size: 11pt;
      line-height: 1.35;
    }
    .receipt { max-width: 80mm; margin: 0 auto; }
    .center { text-align: center; }
    .muted { color: #444; font-size: 9pt; }
    .title { font-size: 14pt; font-weight: 700; margin: 0 0 2mm; }
    .banner {
      border: 2px solid ${esc(primaryColor)};
      color: ${esc(primaryColor)};
      font-weight: 700;
      letter-spacing: 0.04em;
      padding: 2mm;
      margin: 3mm 0;
      text-align: center;
    }
    .rule { border-top: 1px dashed #000; margin: 3mm 0; }
    table { width: 100%; border-collapse: collapse; }
    td { vertical-align: top; padding: 1.5mm 0; }
    td.amt { text-align: right; white-space: nowrap; padding-left: 3mm; }
    .item { font-weight: 700; }
    .meta { font-size: 9pt; color: #333; }
    .empty { color: #666; font-size: 9pt; }
    .totals td { padding-top: 1mm; padding-bottom: 1mm; }
    .totals .strong { font-weight: 700; font-size: 12pt; }
    .foot { margin-top: 4mm; font-size: 9pt; text-align: center; }
    @media print {
      body { padding: 0; }
      .receipt { max-width: none; width: 100%; }
    }
  </style>
</head>
<body>
  <div class="receipt">
    <div class="center">
      <div class="title">${esc(businessName)}</div>
      <div class="muted">${esc(copy.subtitle)}</div>
    </div>
    <div class="banner">${esc(copy.banner)}</div>
    <div><strong>${esc(tx.document_number)}</strong></div>
    <div class="muted">Printed ${esc(printedAt)}</div>
    ${
      customerBits.length
        ? `<div class="rule"></div><div>${customerBits.join("<br/>")}</div>`
        : ""
    }
    ${
      tx.diagnosis_notes?.trim()
        ? `<div class="rule"></div><div class="muted">Complaint / diagnosis</div><div>${esc(tx.diagnosis_notes.trim())}</div>`
        : ""
    }
    <div class="rule"></div>
    <div class="muted">PARTS</div>
    <table>${partRows}</table>
    <div class="rule"></div>
    <div class="muted">LABOR / SERVICE</div>
    <table>${laborRows}</table>
    <div class="rule"></div>
    <table class="totals">
      <tr>
        <td>Parts</td>
        <td class="amt">${money(tx.totals?.parts_total)}</td>
      </tr>
      <tr>
        <td>Labor</td>
        <td class="amt">${money(tx.totals?.labor_total)}</td>
      </tr>
      <tr>
        <td>Gross</td>
        <td class="amt">${money(tx.totals?.gross_total)}</td>
      </tr>
      ${
        Number(tx.totals?.discount_amount ?? 0) > 0
          ? `<tr>
        <td>Discount</td>
        <td class="amt">-${money(tx.totals?.discount_amount)}</td>
      </tr>`
          : ""
      }
      <tr>
        <td class="strong">${variant === "estimate" ? "Estimated total" : "Net total"}</td>
        <td class="amt strong">${money(tx.totals?.net_total)}</td>
      </tr>
      ${
        showPaymentRows
          ? `<tr>
        <td>Paid</td>
        <td class="amt">${money(tx.totals?.paid_total)}</td>
      </tr>
      <tr>
        <td class="strong">Balance due</td>
        <td class="amt strong">${money(tx.totals?.balance_due)}</td>
      </tr>`
          : ""
      }
    </table>
    <div class="foot">${copy.footer}</div>
  </div>
</body>
</html>`;
}

export function printJobDocument(args: PrintJobDocumentArgs) {
  const variant = args.variant ?? "estimate";
  const html = buildJobDocumentHtml({ ...args, variant });
  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const label = variant === "completion" ? "job complete sheet" : "estimate";

  const popup = window.open(url, "_blank", "width=480,height=720");
  if (!popup) {
    URL.revokeObjectURL(url);
    toast.error(`Pop-up blocked — allow pop-ups to print the ${label}`);
    return;
  }

  let printed = false;
  const triggerPrint = () => {
    if (printed) return;
    printed = true;
    try {
      popup.focus();
      popup.print();
    } catch {
      // User can still print manually from the opened tab.
    }
  };

  try {
    popup.addEventListener("load", () => {
      window.setTimeout(triggerPrint, 300);
    });
  } catch {
    // Ignore — fallback timeout below still runs.
  }

  window.setTimeout(triggerPrint, 700);
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

/** @deprecated Prefer printJobDocument({ variant: "estimate" }) */
export function printInitialReceipt(
  args: Omit<PrintJobDocumentArgs, "variant">,
) {
  printJobDocument({ ...args, variant: "estimate" });
}
