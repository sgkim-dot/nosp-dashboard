import {
  getCategoriesLvl1,
  getCategoriesLvl2,
  getKeywordGroups,
  getProducts,
} from "@/lib/db/queries";
import type { ProductCode } from "@/types/bid-decision";
import { FilterBarForm } from "./filter-bar-form";

type FilterBarParams = {
  product: ProductCode;
  categoryLvl1: string | null;
  categoryLvl2: string | null;
  keywordGroupId: number | null;
  lastNRounds: number;
};

export async function FilterBar(props: FilterBarParams) {
  const [allProducts, lvl1, lvl2, kgs] = await Promise.all([
    getProducts(),
    getCategoriesLvl1(props.product),
    props.categoryLvl1 ? getCategoriesLvl2(props.categoryLvl1, props.product) : Promise.resolve([]),
    props.categoryLvl1
      ? getKeywordGroups({
          product: props.product,
          categoryLvl1: props.categoryLvl1,
          categoryLvl2: props.categoryLvl2,
        })
      : Promise.resolve([]),
  ]);

  return (
    <FilterBarForm
      product={props.product}
      categoryLvl1={props.categoryLvl1}
      categoryLvl2={props.categoryLvl2}
      keywordGroupId={props.keywordGroupId}
      lastNRounds={props.lastNRounds}
      products={allProducts.map((p) => ({ code: p.code, name: p.name }))}
      lvl1={lvl1}
      lvl2={lvl2}
      kgs={kgs}
    />
  );
}
