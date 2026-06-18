import { getScrapeMisses, type ScrapeMiss } from "@/lib/db/queries";
import { AlertOctagon, ExternalLink, RefreshCw } from "lucide-react";

export const dynamic = "force-dynamic";

const PRODUCT_LABEL: Record<string, string> = {
  SEARCHING_VIEW: "서칭뷰",
  NEW_PRODUCT: "신제품검색",
  ANNIVERSARY: "기념일",
};

const SEVERITY_META: Record<ScrapeMiss["severity"], { label: string; tone: string; ring: string; desc: string }> = {
  real_miss: {
    label: "진짜 누락",
    tone: "bg-red-50 text-red-700",
    ring: "ring-red-200",
    desc: "스크랩이 광고를 봤지만 추출에 실패. 재시도 필요.",
  },
  never_scraped: {
    label: "스크랩 누락",
    tone: "bg-orange-50 text-orange-700",
    ring: "ring-orange-200",
    desc: "이번 회차에 한 번도 스크랩 안 됨. BAT 재실행 필요.",
  },
  nosp_mismatch: {
    label: "NOSP 메타 불일치",
    tone: "bg-amber-50 text-amber-700",
    ring: "ring-amber-200",
    desc: "우리 스크랩은 광고 다 잡음. NOSP의 슬롯 정원이 실제 운영 광고주 수보다 큼 (정상).",
  },
};

function formatBid(bid: number | null): string {
  if (bid === null) return "—";
  if (bid >= 1_000_000) return `₩${(bid / 1_000_000).toFixed(1)}M`;
  if (bid >= 1_000) return `₩${(bid / 1_000).toFixed(0)}K`;
  return `₩${bid}`;
}

function searchUrl(keyword: string, product: string): string {
  const isMobile = product !== "SEARCHING_VIEW";
  const host = isMobile ? "m.search.naver.com" : "search.naver.com";
  return `https://${host}/search.naver?query=${encodeURIComponent(keyword)}`;
}

export default async function ScrapeMissesPage() {
  const misses = await getScrapeMisses();
  const byType = {
    real_miss: misses.filter((m) => m.severity === "real_miss"),
    never_scraped: misses.filter((m) => m.severity === "never_scraped"),
    nosp_mismatch: misses.filter((m) => m.severity === "nosp_mismatch"),
  };

  return (
    <div>
      <header className="border-b bg-card px-8 py-6">
        <div className="flex items-start gap-3">
          <AlertOctagon className="mt-1 h-7 w-7 text-red-500" />
          <div>
            <h1 className="text-3xl font-bold tracking-tight">광고 누락 의심</h1>
            <p className="mt-1 text-base text-muted-foreground">
              이번 회차 active KG 중 우리 스크랩과 실제 광고 노출이 어긋난 케이스입니다.
              <code className="ml-1.5 rounded bg-muted px-1 py-0.5 font-mono text-xs">detected_slot_count</code>
              는 스크랩이 페이지에서 실제로 본 광고 슬롯 수입니다 (최대 8회 fetch 중 피크).
            </p>
          </div>
        </div>
      </header>

      <div className="space-y-6 px-8 py-6">
        <div className="grid gap-4 sm:grid-cols-3">
          <SummaryCard
            label="진짜 누락"
            count={byType.real_miss.length}
            tone="critical"
            hint="detected > caught"
          />
          <SummaryCard
            label="스크랩 누락"
            count={byType.never_scraped.length}
            tone="warning"
            hint="이번 회차 미실행"
          />
          <SummaryCard
            label="NOSP 메타 불일치"
            count={byType.nosp_mismatch.length}
            tone="neutral"
            hint="우리 스크랩은 정확"
          />
        </div>

        {misses.length === 0 && (
          <div className="rounded-xl border border-dashed bg-emerald-50/40 p-8 text-center">
            <div className="text-lg font-semibold text-emerald-700">
              ✓ 의심 케이스 없음
            </div>
            <div className="mt-1 text-sm text-emerald-600/70">
              이번 회차 active KG 모두 정상 스크랩 또는 NOSP 메타와 일치합니다.
            </div>
          </div>
        )}

        {byType.real_miss.length > 0 && (
          <Section
            title={`🚨 진짜 누락 (${byType.real_miss.length}개)`}
            tone="text-red-700"
            note={SEVERITY_META.real_miss.desc}
            items={byType.real_miss}
          />
        )}
        {byType.never_scraped.length > 0 && (
          <Section
            title={`⏳ 스크랩 누락 (${byType.never_scraped.length}개)`}
            tone="text-orange-700"
            note={SEVERITY_META.never_scraped.desc}
            items={byType.never_scraped}
          />
        )}
        {byType.nosp_mismatch.length > 0 && (
          <Section
            title={`ℹ NOSP 메타 불일치 (${byType.nosp_mismatch.length}개)`}
            tone="text-amber-700"
            note={SEVERITY_META.nosp_mismatch.desc}
            items={byType.nosp_mismatch}
          />
        )}

        <div className="rounded-xl border bg-muted/30 p-4 text-sm text-muted-foreground">
          💡 <strong>진짜 누락</strong>은 강제 재스크랩으로 해결.{" "}
          <code className="rounded bg-background px-1.5 py-0.5 font-mono text-xs">
            scripts/rescrape_overseas_travel.py
          </code>{" "}
          패턴으로 rkg_id만 바꿔서 실행하면 됩니다.{" "}
          <strong>NOSP 메타 불일치</strong>는 NOSP가 슬롯 정원을 2로 잡았지만 실제 광고주는 1명만 운영중인 케이스로,
          단기여행자보험처럼 여러 회차 연속 1/2 패턴이 나오면 정상입니다.
        </div>
      </div>
    </div>
  );
}

function SummaryCard({
  label,
  count,
  tone,
  hint,
}: {
  label: string;
  count: number;
  tone: "critical" | "warning" | "neutral";
  hint?: string;
}) {
  const colors = {
    critical: "border-red-200 bg-red-50/50",
    warning: "border-orange-200 bg-orange-50/50",
    neutral: "border-amber-200 bg-amber-50/50",
  };
  const numColors = {
    critical: "text-red-700",
    warning: "text-orange-700",
    neutral: "text-amber-700",
  };
  return (
    <div className={`rounded-xl border p-5 ${colors[tone]}`}>
      <div className="text-sm font-medium text-muted-foreground">{label}</div>
      <div className={`mt-2 text-4xl font-bold tabular-nums ${numColors[tone]}`}>
        {count}
      </div>
      {hint && <div className="mt-1 text-xs text-muted-foreground">{hint}</div>}
    </div>
  );
}

function Section({
  title,
  tone,
  note,
  items,
}: {
  title: string;
  tone: string;
  note: string;
  items: ScrapeMiss[];
}) {
  return (
    <section>
      <h2 className={`mb-1 text-xl font-semibold ${tone}`}>{title}</h2>
      <p className="mb-3 text-sm text-muted-foreground">{note}</p>
      <div className="space-y-2">
        {items.map((m) => (
          <MissRow key={m.rkgId} m={m} />
        ))}
      </div>
    </section>
  );
}

function MissRow({ m }: { m: ScrapeMiss }) {
  const meta = SEVERITY_META[m.severity];
  return (
    <div className="rounded-xl border bg-card p-4 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <a
            href={searchUrl(m.keywordGroup, m.product)}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-lg font-bold text-primary underline-offset-2 hover:underline"
          >
            {m.keywordGroup}
            <ExternalLink className="h-4 w-4 opacity-70" />
          </a>
          <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
            {PRODUCT_LABEL[m.product] ?? m.product}
          </span>
          <span className="rounded-full bg-muted px-2 py-0.5 font-mono text-xs text-muted-foreground">
            rkg {m.rkgId}
          </span>
          <span
            className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ${meta.tone} ${meta.ring}`}
          >
            {meta.label}
          </span>
        </div>
        <div className="text-sm tabular-nums text-muted-foreground">
          {formatBid(m.regularWinningBid)} 낙찰
        </div>
      </div>
      <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted-foreground">
        <span>
          NOSP 슬롯 <strong className="text-foreground">{m.totalSlots}</strong>
        </span>
        <span>
          페이지에 본 슬롯{" "}
          <strong className="text-foreground">{m.detectedSlotCount}</strong>
        </span>
        <span>
          우리가 잡은 광고주{" "}
          <strong className="text-foreground">{m.caughtCount}</strong>
        </span>
        {m.brandsScrapedAt && (
          <span className="font-mono text-xs">
            <RefreshCw className="mr-0.5 inline h-3 w-3" />
            {m.brandsScrapedAt.slice(0, 16).replace("T", " ")}
          </span>
        )}
      </div>
    </div>
  );
}
