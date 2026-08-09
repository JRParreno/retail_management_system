import { toast } from "sonner";

import { formatPeso } from "@/lib/types";

export type EstimatePartLine = {
  id: string;
  product_id: string;
  name: string;
  barcode: string | null;
  quantity: number;
  unit_price: number;
};

export type EstimateLaborLine = {
  id: string;
  service_name: string;
  description: string | null;
  fee: number;
};

export type EstimateDraft = {
  customer_name: string;
  customer_phone: string;
  motorcycle_model: string;
  plate_number: string;
  motorcycle_color: string;
  diagnosis_notes: string;
  parts: EstimatePartLine[];
  labor: EstimateLaborLine[];
};

function esc(value: string) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function money(value: number) {
  return esc(formatPeso(value));
}

function newId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export function createEmptyEstimate(): EstimateDraft {
  return {
    customer_name: "",
    customer_phone: "",
    motorcycle_model: "",
    plate_number: "",
    motorcycle_color: "",
    diagnosis_notes: "",
    parts: [],
    labor: [],
  };
}

export function estimateId() {
  return newId();
}

export function estimateTotals(draft: EstimateDraft) {
  const parts_total = draft.parts.reduce(
    (sum, line) => sum + line.unit_price * line.quantity,
    0,
  );
  const labor_total = draft.labor.reduce((sum, line) => sum + line.fee, 0);
  return {
    parts_total,
    labor_total,
    net_total: parts_total + labor_total,
  };
}

type PrintEstimateArgs = {
  draft: EstimateDraft;
  businessName?: string;
  primaryColor?: string;
};

export function printEstimateDocument({
  draft,
  businessName = "MotoShop RMS",
  primaryColor = "#C26A1A",
}: PrintEstimateArgs) {
  const totals = estimateTotals(draft);
  if (!draft.parts.length && !draft.labor.length) {
    toast.error("Add at least one part or service before printing");
    return;
  }

  const printedAt = new Date().toLocaleString();
  const ref = `EST-${new Date().toISOString().slice(0, 10).replace(/-/g, "")}-${String(
    Date.now(),
  ).slice(-4)}`;

  const partRows = draft.parts.length
    ? draft.parts
        .map((line) => {
          const lineTotal = line.unit_price * line.quantity;
          return `<tr>
            <td>
              <div class="item">${esc(line.name)}</div>
              ${line.barcode ? `<div class="meta">${esc(line.barcode)}</div>` : ""}
              <div class="meta">x ${line.quantity} @ ${money(line.unit_price)}</div>
            </td>
            <td class="amt">${money(lineTotal)}</td>
          </tr>`;
        })
        .join("")
    : `<tr><td colspan="2" class="empty">No parts</td></tr>`;

  const laborRows = draft.labor.length
    ? draft.labor
        .map((line) => {
          const desc = line.description?.trim();
          return `<tr>
            <td>
              <div class="item">${esc(line.service_name)}</div>
              ${desc ? `<div class="meta">${esc(desc)}</div>` : ""}
            </td>
            <td class="amt">${money(line.fee)}</td>
          </tr>`;
        })
        .join("")
    : `<tr><td colspan="2" class="empty">No labor / service</td></tr>`;

  const customerBits = [
    draft.customer_name,
    draft.customer_phone,
    draft.motorcycle_model,
    draft.plate_number,
    draft.motorcycle_color,
  ]
    .filter((v) => v.trim())
    .map((v) => esc(v.trim()));

  const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Estimate ${esc(ref)}</title>
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
      <div class="muted">Parts &amp; labor estimate</div>
    </div>
    <div class="banner">SERVICE ESTIMATE</div>
    <div><strong>${esc(ref)}</strong></div>
    <div class="muted">Printed ${esc(printedAt)}</div>
    <div class="muted">Not saved to system — quote only</div>
    ${
      customerBits.length
        ? `<div class="rule"></div><div>${customerBits.join("<br/>")}</div>`
        : ""
    }
    ${
      draft.diagnosis_notes.trim()
        ? `<div class="rule"></div><div class="muted">Complaint / notes</div><div>${esc(draft.diagnosis_notes.trim())}</div>`
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
        <td class="amt">${money(totals.parts_total)}</td>
      </tr>
      <tr>
        <td>Labor</td>
        <td class="amt">${money(totals.labor_total)}</td>
      </tr>
      <tr>
        <td class="strong">Estimated total</td>
        <td class="amt strong">${money(totals.net_total)}</td>
      </tr>
    </table>
    <div class="foot">
      Estimate only — not saved as a job.<br/>
      Amounts may change after inspection or approval.<br/>
      Not a final official receipt.
    </div>
  </div>
</body>
</html>`;

  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const popup = window.open(url, "_blank", "width=480,height=720");
  if (!popup) {
    URL.revokeObjectURL(url);
    toast.error("Pop-up blocked — allow pop-ups to print the estimate");
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
      // Manual print still available.
    }
  };

  try {
    popup.addEventListener("load", () => {
      window.setTimeout(triggerPrint, 300);
    });
  } catch {
    // fallback below
  }

  window.setTimeout(triggerPrint, 700);
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
