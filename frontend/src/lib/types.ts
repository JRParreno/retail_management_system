export type Role = "ADMIN" | "CASHIER";

export type User = {
  id: string;
  username: string;
  full_name: string;
  role: Role;
  branch_id: string;
  is_active: boolean;
  created_at: string;
};

export type Branch = {
  id: string;
  code: string;
  name: string;
  address: string | null;
  phone: string | null;
  is_active: boolean;
  created_at: string;
  updated_at?: string;
};

export type StockTransferLine = {
  id: string;
  product_id: string;
  quantity: number;
  product_name?: string | null;
  product_barcode?: string | null;
};

export type StockTransfer = {
  id: string;
  document_number: string;
  from_branch_id: string;
  to_branch_id: string;
  notes: string | null;
  created_by_id: string;
  created_at: string;
  lines: StockTransferLine[];
};

export type Mechanic = {
  id: string;
  full_name: string;
  nickname: string;
  default_commission_rate: string;
  is_active: boolean;
  created_at: string;
};

export type MechanicProfileLaborLine = {
  id: string;
  transaction_id: string;
  document_number: string | null;
  service_name: string;
  description: string | null;
  original_price: string;
  actual_price: string;
  mechanic_commission_rate: string | null;
  mechanic_payout_amount: string | null;
  customer_name: string | null;
  customer_phone: string | null;
  motorcycle_model: string | null;
  plate_number: string | null;
  motorcycle_color: string | null;
  created_at: string;
  paid_at: string | null;
};

export type MechanicProfile = {
  id: string;
  full_name: string;
  nickname: string;
  default_commission_rate: string;
  is_active: boolean;
  start_date: string;
  end_date: string;
  job_count: number;
  labor_sales: string;
  commission_total: string;
  recent_lines: MechanicProfileLaborLine[];
};

export type Product = {
  id: string;
  barcode: string;
  name: string;
  brand: string | null;
  image_url: string | null;
  cost_price: string;
  current_selling_price: string;
  stock_qty: number;
  min_stock_threshold: number;
  category_id: string | null;
  is_active: boolean;
  deleted_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ProductDeletionImpact = {
  product_id: string;
  can_hard_delete: boolean;
  catalog_stock: number;
  branch_stock: number;
  transaction_lines: number;
  stock_adjustments: number;
  transfer_lines: number;
  return_lines: number;
};

export type ProductCategory = {
  id: string;
  name: string;
  created_at: string;
};

export type TransactionStatus = "IN_PROGRESS" | "DONE" | "PAID" | "CANCELLED";
export type TransactionType = "DIRECT_SALE" | "SERVICE_JOB";
export type PaymentMethod = "CASH" | "GCASH" | "BANK_TRANSFER" | "CARD" | "OTHER";

export type TransactionPartLine = {
  id: string;
  transaction_id: string;
  product_id: string;
  quantity: number;
  cost_price_snapshot: string;
  original_selling_price: string;
  actual_selling_price: string;
  override_reason: string | null;
  created_at: string;
};

export type TransactionLaborLine = {
  id: string;
  transaction_id: string;
  service_name: string;
  description: string | null;
  labor_fee: string;
  mechanic_id: string | null;
  mechanic_commission_rate: string | null;
  mechanic_payout_amount: string | null;
  original_price: string;
  actual_price: string;
  override_reason: string | null;
  created_at: string;
};

export type Payment = {
  id: string;
  transaction_id: string;
  payment_method: PaymentMethod;
  amount: string;
  amount_tendered: string | null;
  change_due: string | null;
  received_by_id: string;
  paid_at: string;
  reference_no: string | null;
  proof_image_url: string | null;
  notes: string | null;
  created_at: string;
};

export type TransactionTotals = {
  parts_total: string;
  labor_total: string;
  gross_total: string;
  discount_amount: string;
  net_total: string;
  paid_total: string;
  balance_due: string;
};

export type Transaction = {
  id: string;
  document_number: string;
  transaction_type: TransactionType;
  status: TransactionStatus;
  cashier_id: string;
  shift_id: string | null;
  customer_name: string | null;
  customer_phone: string | null;
  motorcycle_model: string | null;
  plate_number: string | null;
  motorcycle_color: string | null;
  odometer_km: number | null;
  diagnosis_notes: string | null;
  internal_notes: string | null;
  estimated_total: string | null;
  discount_amount: string;
  discount_reason: string | null;
  started_at: string | null;
  completed_at: string | null;
  paid_at: string | null;
  created_at: string;
  updated_at: string;
  part_lines: TransactionPartLine[];
  labor_lines: TransactionLaborLine[];
  payments?: Payment[];
  totals?: TransactionTotals;
};

export type CashierShift = {
  id: string;
  cashier_id: string;
  opening_float: string;
  closing_cash_counted: string | null;
  expected_cash: string | null;
  status: "OPEN" | "CLOSED";
  opened_at: string;
  closed_at: string | null;
  scheduled_end_at: string | null;
  close_timing: "ON_TIME" | "EARLY" | "EXTENDED" | null;
  close_notes: string | null;
  first_mechanic_id: string | null;
};

export type Paginated<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
};

export type ReportSummary = {
  gross_revenue: string;
  cogs: string;
  gross_profit: string;
  parts_sales: string;
  labor_sales: string;
  parts_profit: string;
  labor_profit_before_commission: string;
  net_profit: string;
  avg_ticket: string;
  commission_total: string;
  commission_gross_total: string;
  commission_waived_total: string;
  low_stock_count: number;
  transaction_count: number;
  mechanic_commissions: MechanicCommissionRow[];
  product_sales: ProductSalesRow[];
};

export type RefundablePartLine = {
  part_line_id: string;
  product_id: string;
  product_name: string | null;
  barcode: string | null;
  original_qty: number;
  returned_qty: number;
  remaining_qty: number;
  unit_price: string;
  cost_price: string;
};

export type RefundableLaborLine = {
  labor_line_id: string;
  service_name: string;
  mechanic_id: string | null;
  actual_price: string;
  mechanic_payout_amount: string;
  already_refunded: boolean;
};

export type RefundableSnapshot = {
  transaction_id: string;
  document_number: string;
  status: string;
  branch_id: string;
  part_lines: RefundablePartLine[];
  labor_lines: RefundableLaborLine[];
};

export type ReturnVoidPartLine = {
  id: string;
  return_void_id: string;
  original_part_line_id: string | null;
  product_id: string;
  quantity: number;
  restock: boolean;
  unit_refund_amount: string;
  cost_price_snapshot: string;
};

export type ReturnVoidLaborLine = {
  id: string;
  return_void_id: string;
  original_labor_line_id: string | null;
  mechanic_id: string | null;
  refund_amount: string;
  commission_reversal_amount: string;
};

export type ReturnVoid = {
  id: string;
  document_number: string;
  original_transaction_id: string;
  return_type: "VOID" | "PARTIAL_RETURN";
  status: "COMPLETED";
  reason: string;
  processed_by_id: string;
  cashier_id: string;
  shift_id: string | null;
  created_at: string;
  part_lines: ReturnVoidPartLine[];
  labor_lines: ReturnVoidLaborLine[];
};

export type ShopSettings = {
  business_name: string;
  primary_color: string;
  cashier_shift_start: string;
  cashier_shift_end: string;
  waive_first_mechanic_commission: boolean;
};

export type MechanicCommissionRow = {
  mechanic_id: string;
  nickname: string;
  labor_sales: string;
  commission_gross: string;
  commission_waived: string;
  commission_total: string;
  line_count: number;
  is_first_mechanic_waived: boolean;
};

export type ProductSalesRow = {
  product_id: string;
  product_name: string;
  barcode: string;
  brand: string | null;
  quantity_sold: number;
  sales_total: string;
  cogs_total: string;
  profit: string;
  line_count: number;
};

export type MechanicCommissionComputation = {
  mechanic_id: string;
  nickname: string;
  labor_sales: string;
  commission_gross: string;
  commission_waived: string;
  commission_net: string;
  line_count: number;
  is_first_mechanic: boolean;
  commission_waived_for_policy: boolean;
};

export type CommissionComputationReport = {
  day: string;
  policy_enabled: boolean;
  applied: boolean;
  first_mechanic_id: string | null;
  first_mechanic_nickname: string | null;
  mechanics: MechanicCommissionComputation[];
  labor_sales_total: string;
  commission_gross_total: string;
  commission_waived_total: string;
  commission_net_total: string;
};

export function formatPeso(value: string | number | null | undefined) {
  const n = typeof value === "string" ? Number(value) : value ?? 0;
  return new Intl.NumberFormat("en-PH", {
    style: "currency",
    currency: "PHP",
    minimumFractionDigits: 2,
  }).format(Number.isFinite(n) ? n : 0);
}
