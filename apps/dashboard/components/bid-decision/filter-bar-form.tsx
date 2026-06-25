"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";
import type { ProductCode } from "@/types/bid-decision";
import { KgSearchCombobox, type KgSearchItem } from "./kg-search-combobox";

const RANGE_OPTIONS = [6, 12, 24, 52];

type Props = {
  product: ProductCode;
  categoryLvl1: string | null;
  categoryLvl2: string | null;
  keywordGroupId: number | null;
  lastNRounds: number;
  products: { code: string; name: string }[];
  lvl1: { id: number; name: string }[];
  lvl2: { id: number; name: string }[];
  kgs: { id: number; name: string }[];
  allKgs: KgSearchItem[];
};

export function FilterBarForm(props: Props) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  function applyParams(updates: Record<string, string | null>) {
    const params = new URLSearchParams();
    const merged: Record<string, string | null> = {
      product: props.product,
      cat1: props.categoryLvl1,
      cat2: props.categoryLvl2,
      kg: props.keywordGroupId?.toString() ?? null,
      last: String(props.lastNRounds),
      ...updates,
    };
    for (const [k, v] of Object.entries(merged)) {
      if (v != null && v !== "") params.set(k, v);
    }
    startTransition(() => {
      router.push(`/?${params.toString()}`);
    });
  }

  return (
    <div
      className={`flex flex-wrap items-end gap-4 border-b bg-card px-8 py-5 ${pending ? "opacity-60" : ""}`}
    >
      <Field label="제품">
        <select
          value={props.product}
          className={selectCls}
          onChange={(e) =>
            applyParams({
              product: e.target.value,
              cat1: null,
              cat2: null,
              kg: null,
            })
          }
        >
          {props.products.map((p) => (
            <option key={p.code} value={p.code}>
              {p.name}
            </option>
          ))}
        </select>
      </Field>

      <Field label="대분류">
        <select
          value={props.categoryLvl1 ?? ""}
          className={selectCls}
          onChange={(e) =>
            applyParams({
              cat1: e.target.value || null,
              cat2: null,
              kg: null,
            })
          }
        >
          <option value="">(전체)</option>
          {props.lvl1.map((c) => (
            <option key={c.id} value={c.name}>
              {c.name}
            </option>
          ))}
        </select>
      </Field>

      <Field label="소분류">
        <select
          value={props.categoryLvl2 ?? ""}
          className={selectCls}
          disabled={!props.categoryLvl1}
          onChange={(e) =>
            applyParams({
              cat2: e.target.value || null,
              kg: null,
            })
          }
        >
          <option value="">(전체)</option>
          {props.lvl2.map((c) => (
            <option key={c.id} value={c.name}>
              {c.name}
            </option>
          ))}
        </select>
      </Field>

      <Field label="키워드그룹">
        <select
          value={props.keywordGroupId?.toString() ?? ""}
          className={`${selectCls} min-w-[16rem]`}
          disabled={!props.categoryLvl1}
          onChange={(e) =>
            applyParams({
              kg: e.target.value || null,
            })
          }
        >
          <option value="">(선택)</option>
          {props.kgs.map((kg) => (
            <option key={kg.id} value={kg.id}>
              {kg.name}
            </option>
          ))}
        </select>
      </Field>

      <Field label="기간">
        <select
          value={String(props.lastNRounds)}
          className={selectCls}
          onChange={(e) => applyParams({ last: e.target.value })}
        >
          {RANGE_OPTIONS.map((n) => (
            <option key={n} value={n}>
              최근 {n}회차
            </option>
          ))}
        </select>
      </Field>

      <div className="flex w-[22rem] flex-col gap-2">
        <span className="text-base font-semibold text-foreground">빠른 검색</span>
        <KgSearchCombobox
          items={props.allKgs}
          product={props.product}
          lastNRounds={props.lastNRounds}
          selectedKgId={props.keywordGroupId}
        />
      </div>

      {pending && (
        <span className="text-sm text-muted-foreground">로딩 중…</span>
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-2">
      <span className="text-base font-semibold text-foreground">{label}</span>
      {children}
    </label>
  );
}

const selectCls =
  "rounded-lg border border-input bg-background px-3.5 py-2.5 text-base outline-none transition focus:ring-2 focus:ring-ring hover:border-ring/50 disabled:opacity-50 disabled:cursor-not-allowed";
