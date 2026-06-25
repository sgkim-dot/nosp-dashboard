"use client";

import { useState } from "react";
import { Download, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { RoundRow } from "@/types/bid-decision";

function todayYMD(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function sanitizeFilename(s: string): string {
  return s.replace(/[\\/:*?"<>|]/g, "_").trim() || "keyword-group";
}

export function RoundDownloadButton({
  rounds,
  keywordGroupName,
}: {
  rounds: RoundRow[];
  keywordGroupName: string;
}) {
  const [busy, setBusy] = useState(false);

  const handleDownload = async () => {
    if (rounds.length === 0 || busy) return;
    setBusy(true);
    try {
      const XLSX = await import("xlsx");
      const ordered = [...rounds].reverse();

      const summaryRows: (string | number)[][] = [
        [
          "회차",
          "집행기간",
          "기준조회수",
          "최저(VAT-)",
          "낙찰(VAT-)",
          "배수",
          "공실(구좌수)",
          "집행브랜드",
          "상태",
        ],
        ...ordered.map((r) => [
          r.roundNo,
          `${r.periodStart} ~ ${r.periodEnd}`,
          r.referenceQueryVolume ?? "",
          r.minBidPrice ?? "",
          r.regularWinningBid ?? "",
          r.ratio ?? "",
          r.emptySlots ?? "",
          r.brands.map((b) => b.displayName).join(" / "),
          r.bidStatus ?? "",
        ]),
      ];
      const summarySheet = XLSX.utils.aoa_to_sheet(summaryRows);
      summarySheet["!cols"] = [
        { wch: 8 },
        { wch: 24 },
        { wch: 12 },
        { wch: 14 },
        { wch: 14 },
        { wch: 8 },
        { wch: 12 },
        { wch: 36 },
        { wch: 12 },
      ];

      const detailRows: (string | number)[][] = [
        [
          "회차",
          "회차기간",
          "슬롯번호",
          "표시명",
          "광고타이틀",
          "부타이틀",
          "본문",
          "사업자명",
          "출처",
          "신뢰도",
        ],
      ];
      for (const r of ordered) {
        for (const b of r.brands) {
          detailRows.push([
            r.roundNo,
            `${r.periodStart} ~ ${r.periodEnd}`,
            b.slotNo,
            b.displayName,
            b.title,
            b.subTitle ?? "",
            b.description ?? "",
            b.businessName,
            b.source,
            b.confidence ?? "",
          ]);
        }
      }
      const detailSheet = XLSX.utils.aoa_to_sheet(detailRows);
      detailSheet["!cols"] = [
        { wch: 8 },
        { wch: 24 },
        { wch: 8 },
        { wch: 18 },
        { wch: 40 },
        { wch: 28 },
        { wch: 40 },
        { wch: 22 },
        { wch: 14 },
        { wch: 10 },
      ];

      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, summarySheet, "회차 요약");
      XLSX.utils.book_append_sheet(wb, detailSheet, "집행사 상세");

      const filename = `${sanitizeFilename(keywordGroupName)}_회차내역_${todayYMD()}.xlsx`;
      XLSX.writeFile(wb, filename);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Button
      variant="outline"
      size="sm"
      onClick={handleDownload}
      disabled={rounds.length === 0 || busy}
      aria-label="엑셀로 다운로드"
    >
      {busy ? <Loader2 className="animate-spin" /> : <Download />}
      <span>엑셀 다운로드</span>
    </Button>
  );
}
