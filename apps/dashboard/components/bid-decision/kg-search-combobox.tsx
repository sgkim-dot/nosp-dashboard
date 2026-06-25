"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { Search, X } from "lucide-react";

export type KgSearchItem = {
  id: number;
  name: string;
  cat1: string;
  cat2: string;
};

type Props = {
  items: KgSearchItem[];
  product: string;
  lastNRounds: number;
  selectedKgId: number | null;
};

const MAX_RESULTS = 12;

export function KgSearchCombobox({ items, product, lastNRounds, selectedKgId }: Props) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (selectedKgId == null) {
      setQuery("");
      return;
    }
    const cur = items.find((i) => i.id === selectedKgId);
    if (cur) setQuery(cur.name);
  }, [selectedKgId, items]);

  useEffect(() => {
    function onDocDown(e: MouseEvent) {
      if (!rootRef.current) return;
      if (!rootRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDocDown);
    return () => document.removeEventListener("mousedown", onDocDown);
  }, []);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items.slice(0, MAX_RESULTS);
    const matched: KgSearchItem[] = [];
    for (const it of items) {
      const hay = `${it.name} ${it.cat1} ${it.cat2}`.toLowerCase();
      if (hay.includes(q)) matched.push(it);
      if (matched.length >= MAX_RESULTS) break;
    }
    return matched;
  }, [query, items]);

  function jumpTo(it: KgSearchItem) {
    const params = new URLSearchParams({
      product,
      cat1: it.cat1,
      cat2: it.cat2,
      kg: String(it.id),
      last: String(lastNRounds),
    });
    setQuery(it.name);
    setOpen(false);
    router.push(`/?${params.toString()}`);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setActive((a) => Math.min(a + 1, Math.max(0, results.length - 1)));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter") {
      const it = results[active];
      if (it) {
        e.preventDefault();
        jumpTo(it);
      }
    } else if (e.key === "Escape") {
      setOpen(false);
      inputRef.current?.blur();
    }
  }

  function clear() {
    setQuery("");
    setActive(0);
    setOpen(true);
    inputRef.current?.focus();
  }

  return (
    <div ref={rootRef} className="relative w-full max-w-md">
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <input
          ref={inputRef}
          type="text"
          value={query}
          placeholder="키워드그룹 검색 (이름·대/소분류)"
          onChange={(e) => {
            setQuery(e.target.value);
            setActive(0);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          className="w-full rounded-lg border border-input bg-background pl-9 pr-9 py-2.5 text-base outline-none transition focus:ring-2 focus:ring-ring hover:border-ring/50"
        />
        {query && (
          <button
            type="button"
            onClick={clear}
            className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
            aria-label="검색어 지우기"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {open && (
        <div className="absolute left-0 right-0 top-full z-30 mt-1 max-h-80 overflow-auto rounded-lg border bg-popover shadow-lg">
          {results.length === 0 ? (
            <div className="px-3 py-3 text-sm text-muted-foreground">
              매칭되는 키워드그룹이 없습니다.
            </div>
          ) : (
            <ul className="py-1">
              {results.map((it, idx) => {
                const isActive = idx === active;
                return (
                  <li key={it.id}>
                    <button
                      type="button"
                      onMouseEnter={() => setActive(idx)}
                      onClick={() => jumpTo(it)}
                      className={`flex w-full flex-col items-start gap-0.5 px-3 py-2 text-left text-sm transition ${
                        isActive ? "bg-accent" : "hover:bg-accent/60"
                      }`}
                    >
                      <span className="font-medium text-foreground">{it.name}</span>
                      <span className="text-xs text-muted-foreground">
                        {it.cat1} · {it.cat2}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
