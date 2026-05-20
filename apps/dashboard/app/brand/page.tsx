import { CategoryHeatmap } from "@/components/brand/category-heatmap";
import {
  getBrandHeatmap,
  getCategoriesLvl1,
  getProducts,
} from "@/lib/db/queries";
import type { ProductCode } from "@/types/bid-decision";
import { BrandFilterForm } from "@/components/brand/brand-filter-form";

export const dynamic = "force-dynamic";

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

function pickStr(v: string | string[] | undefined): string | null {
  if (Array.isArray(v)) return v[0] ?? null;
  return v ?? null;
}

export default async function BrandPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const sp = await searchParams;
  const product = (pickStr(sp.product) as ProductCode | null) ?? "SEARCHING_VIEW";
  const cat1 = pickStr(sp.cat1);
  const lastN = Number(pickStr(sp.last) ?? 8);

  const [allProducts, lvl1, heatmap] = await Promise.all([
    getProducts(),
    getCategoriesLvl1(),
    getBrandHeatmap({ product, categoryLvl1: cat1, lastNRounds: lastN }),
  ]);

  return (
    <div>
      <header className="border-b px-6 py-3">
        <h1 className="text-lg font-semibold">브랜드 점유</h1>
        <p className="text-xs text-muted-foreground">
          카테고리 단위 회차별 집행 브랜드 변화를 확인합니다.
        </p>
      </header>

      <BrandFilterForm
        product={product}
        categoryLvl1={cat1}
        lastNRounds={lastN}
        products={allProducts.map((p) => ({ code: p.code, name: p.name }))}
        lvl1={lvl1}
      />

      <div className="space-y-4 px-6 py-4">
        <CategoryHeatmap rows={heatmap} />
      </div>
    </div>
  );
}
