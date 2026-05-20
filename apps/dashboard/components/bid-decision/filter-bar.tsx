import {
  getCategoriesLvl1,
  getCategoriesLvl2,
  getKeywordGroups,
  getProducts,
} from "@/lib/db/queries";
import type { ProductCode } from "@/types/bid-decision";

type FilterBarParams = {
  product: ProductCode;
  categoryLvl1: string | null;
  categoryLvl2: string | null;
  keywordGroupId: number | null;
  lastNRounds: number;
};

const RANGE_OPTIONS = [6, 12, 24, 52];

export async function FilterBar(props: FilterBarParams) {
  const [allProducts, lvl1, lvl2, kgs] = await Promise.all([
    getProducts(),
    getCategoriesLvl1(),
    props.categoryLvl1 ? getCategoriesLvl2(props.categoryLvl1) : Promise.resolve([]),
    props.categoryLvl1
      ? getKeywordGroups({
          product: props.product,
          categoryLvl1: props.categoryLvl1,
          categoryLvl2: props.categoryLvl2,
        })
      : Promise.resolve([]),
  ]);

  return (
    <form
      method="GET"
      action="/"
      className="flex flex-wrap items-end gap-2 border-b bg-background/95 px-6 py-3 text-sm"
    >
      <Field label="제품">
        <select name="product" defaultValue={props.product} className={selectCls}>
          {allProducts.map((p) => (
            <option key={p.code} value={p.code}>
              {p.name}
            </option>
          ))}
        </select>
      </Field>

      <Field label="대분류">
        <select
          name="cat1"
          defaultValue={props.categoryLvl1 ?? ""}
          className={selectCls}
        >
          <option value="">(전체)</option>
          {lvl1.map((c) => (
            <option key={c.id} value={c.name}>
              {c.name}
            </option>
          ))}
        </select>
      </Field>

      <Field label="소분류">
        <select
          name="cat2"
          defaultValue={props.categoryLvl2 ?? ""}
          className={selectCls}
          disabled={!props.categoryLvl1}
        >
          <option value="">(전체)</option>
          {lvl2.map((c) => (
            <option key={c.id} value={c.name}>
              {c.name}
            </option>
          ))}
        </select>
      </Field>

      <Field label="키워드그룹">
        <select
          name="kg"
          defaultValue={props.keywordGroupId?.toString() ?? ""}
          className={`${selectCls} min-w-[14rem]`}
          disabled={!props.categoryLvl1}
        >
          <option value="">(선택)</option>
          {kgs.map((kg) => (
            <option key={kg.id} value={kg.id}>
              {kg.name}
            </option>
          ))}
        </select>
      </Field>

      <Field label="기간">
        <select
          name="last"
          defaultValue={String(props.lastNRounds)}
          className={selectCls}
        >
          {RANGE_OPTIONS.map((n) => (
            <option key={n} value={n}>
              최근 {n}회차
            </option>
          ))}
        </select>
      </Field>

      <button
        type="submit"
        className="ml-auto rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90"
      >
        적용
      </button>
    </form>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs text-muted-foreground">{label}</span>
      {children}
    </label>
  );
}

const selectCls =
  "rounded-md border border-input bg-background px-2 py-1.5 text-sm outline-none focus:ring-2 focus:ring-ring";
