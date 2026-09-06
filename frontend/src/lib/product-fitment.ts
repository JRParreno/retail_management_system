import type { Product } from "@/lib/types";

export type ProductFitmentModel = {
  id: string;
  brand: string;
  name: string;
  display_name: string;
};

/** Human-readable fitment line for POS / jobs / inventory. */
export function formatProductFits(
  models: ProductFitmentModel[] | null | undefined,
): string {
  const names = (models ?? [])
    .map((m) => m.display_name.trim())
    .filter(Boolean);
  if (names.length === 0) return "";
  return `Fits: ${names.join(", ")}`;
}

export function productFitmentKeywords(
  product: Pick<Product, "applicable_motorcycle_models">,
): string {
  return (product.applicable_motorcycle_models ?? [])
    .map((m) => `${m.display_name} ${m.brand} ${m.name}`)
    .join(" ");
}
