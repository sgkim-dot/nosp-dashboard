"use client";

import { useEffect, useState } from "react";
import type { RoundRow } from "@/types/bid-decision";
import { RoundTable } from "./round-table";
import { RoundDetailPanel } from "./round-detail-panel";
import { RoundDownloadButton } from "./round-download-button";

export function RoundsWithDetail({
  rounds,
  keywordGroupName,
  defaultSelectedId: _defaultSelectedId,
}: {
  rounds: RoundRow[];
  keywordGroupName: string;
  // kept for API stability — the floating modal opens on demand, not by default
  defaultSelectedId: number | null;
}) {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const selected = rounds.find((r) => r.roundId === selectedId) ?? null;
  const isOpen = selected !== null;

  // Esc to close, lock background scroll while open
  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSelectedId(null);
    };
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [isOpen]);

  return (
    <>
      <div className="mb-2 flex justify-end">
        <RoundDownloadButton
          rounds={rounds}
          keywordGroupName={keywordGroupName}
        />
      </div>
      <RoundTable
        rounds={rounds}
        selectedRoundId={selectedId}
        onSelect={setSelectedId}
      />

      {isOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 animate-in fade-in duration-150"
          onClick={() => setSelectedId(null)}
        >
          <div
            className="w-full max-w-2xl max-h-[88vh] overflow-y-auto rounded-2xl shadow-2xl animate-in zoom-in-95 duration-150"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="relative">
              <button
                type="button"
                onClick={() => setSelectedId(null)}
                aria-label="닫기"
                className="absolute right-4 top-4 z-10 grid h-9 w-9 place-items-center rounded-full text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18 6L6 18M6 6l12 12" />
                </svg>
              </button>
              <RoundDetailPanel round={selected} />
            </div>
          </div>
        </div>
      )}
    </>
  );
}
