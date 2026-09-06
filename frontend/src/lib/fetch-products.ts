import { clientApi } from "@/lib/client-api";
import type { Paginated, Product } from "@/lib/types";

/** Safe page size for older APIs that capped `page_size` at 500 (or lower). */
export const PRODUCT_FETCH_PAGE_SIZE = 100;

type FetchProductsOptions = {
  /** Extra query string without leading `?` / `&` (e.g. `lifecycle=all`). */
  query?: string;
  pageSize?: number;
};

/**
 * Load every matching product by paging.
 * Works with backends that only allow page_size ≤ 500 (or 100).
 */
export async function fetchAllProducts(
  options: FetchProductsOptions = {},
): Promise<Product[]> {
  const pageSize = options.pageSize ?? PRODUCT_FETCH_PAGE_SIZE;
  const extra = options.query?.replace(/^[?&]/, "") ?? "";
  let page = 1;
  let collected: Product[] = [];
  let total = Infinity;

  while (collected.length < total) {
    const params = new URLSearchParams();
    params.set("page", String(page));
    params.set("page_size", String(pageSize));
    const qs = extra ? `${params}&${extra}` : params.toString();
    const res = await clientApi<Paginated<Product>>(`/products?${qs}`);
    total = res.total;
    collected = collected.concat(res.items ?? []);
    if (!res.items?.length || collected.length >= total) break;
    page += 1;
  }

  return collected;
}
