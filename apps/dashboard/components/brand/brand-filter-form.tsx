"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";
import type { ProductCode } from "@/types/bid-decision";

type Props = {
  product: ProductCode;
  categoryLvl1: string | null;
  lastNRounds: number;
  products: { code: string; name: string }[];
  lvl1: { id: number; name: string }[];
};

const RANGE_OPTIONS = [6, 8, 12, 24];

export function BrandFilterForm(props: Props) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  function apply(updates: Record<string, string | null>) {
    const merged: Record<string, string | null> = {
      product: props.product,
      cat1: props.categoryLvl1,
      last: String(props.lastNRounds),
      ...updates,
    };
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(merged)) {
      if (v != null && v !== "") params.set(k, v);
    }
    startTransition(() => {
      router.push(`/brand?${params.toString()}`);
    });
  }

  return (
    <div
      className={`flex flex-wrap items-end gap-2 border-b bg-background/95 px-6 py-3 text-sm ${
        pending ? "opacity-60" : ""
      }`}
    >
      <label className="flex flex-col gap-1">
        <span className="text-xs text-muted-foreground">제품</span>
        <select
          value={props.product}
          className={selectCls}
          onChange={(e) => apply({ product: e.target.value, cat1: null })}
        >
          {props.products.map((p) => (
            <option key={p.code} value={p.code}>
              {p.name}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-xs text-muted-foreground">대분류</span>
        <select
          value={props.categoryLvl1 ?? ""}
          className={selectCls}
          onChange={(e) => apply({ cat1: e.target.value || null })}
        >
          <option value="">(전체)</option>
          {props.lvl1.map((c) => (
            <option key={c.id} value={c.name}>
              {c.name}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-xs text-muted-foreground">기간</span>
        <select
          value={String(props.lastNRounds)}
          className={selectCls}
          onChange={(e) => apply({ last: e.target.value })}
        >
          {RANGE_OPTIONS.map((n) => (
            <option key={n} value={n}>
              최근 {n}회차
            </option>
          ))}
        </select>
      </label>

      {pending && (
        <span className="ml-auto text-xs text-muted-foreground">로딩 중…</span>
      )}
    </div>
  );
}

const selectCls =
  "rounded-md border border-input bg-background px-2 py-1.5 text-sm outline-none focus:ring-2 focus:ring-ring";
