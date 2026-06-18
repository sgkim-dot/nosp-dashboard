import { getSuspectBrands } from "@/lib/db/queries";
import { CrawlAutoRefresh } from "@/components/crawl/auto-refresh";
import { AlertTriangle, ExternalLink } from "lucide-react";

export const dynamic = "force-dynamic";

function urlFor(host: string, isBroken: boolean): string | null {
  if (isBroken) return null;
  if (host.startsWith("http")) return host;
  return `https://${host}`;
}

function reasonBadge(reason: string) {
  const tones: Record<string, string> = {
    "호스트 깨짐": "bg-red-50 text-red-700 ring-red-200",
    "미확인 브랜드": "bg-red-50 text-red-700 ring-red-200",
    "짧은 이름": "bg-amber-50 text-amber-700 ring-amber-200",
    "hook 단어": "bg-amber-50 text-amber-700 ring-amber-200",
    "sub_title과 불일치": "bg-amber-50 text-amber-700 ring-amber-200",
  };
  const tone = tones[reason] ?? "bg-muted text-muted-foreground ring-border";
  return (
    <span
      key={reason}
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ${tone}`}
    >
      {reason}
    </span>
  );
}

const PRODUCT_LABEL: Record<string, string> = {
  SEARCHING_VIEW: "서칭뷰",
  NEW_PRODUCT: "신제품검색",
  ANNIVERSARY: "기념일",
};

export default async function BrandCleanupPage() {
  const suspects = await getSuspectBrands();

  // Group by severity
  const critical = suspects.filter(
    (s) => s.reasons.includes("호스트 깨짐") || s.reasons.includes("미확인 브랜드"),
  );
  const warnings = suspects.filter(
    (s) => !s.reasons.includes("호스트 깨짐") && !s.reasons.includes("미확인 브랜드"),
  );

  return (
    <div>
      <header className="border-b bg-card px-8 py-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="flex items-center gap-2 text-3xl font-bold tracking-tight">
              <AlertTriangle className="h-7 w-7 text-amber-500" />
              브랜드 정리 필요
            </h1>
            <p className="mt-1 text-base text-muted-foreground">
              자동 추정한 브랜드명이 잘못됐을 가능성이 있는 케이스입니다.
              URL을 확인하고 매핑이 필요하면 알려주세요.
            </p>
          </div>
          <CrawlAutoRefresh intervalSec={60} />
        </div>
      </header>

      <div className="space-y-6 px-8 py-6">
        {/* Summary */}
        <div className="grid gap-4 sm:grid-cols-3">
          <SummaryCard
            label="긴급 정정 필요"
            count={critical.length}
            tone="critical"
            hint="호스트 깨짐 또는 미확인"
          />
          <SummaryCard
            label="검토 필요"
            count={warnings.length}
            tone="warning"
            hint="첫단어 휴리스틱 추정"
          />
          <SummaryCard
            label="전체 의심 케이스"
            count={suspects.length}
            tone="neutral"
          />
        </div>

        {suspects.length === 0 && (
          <div className="rounded-xl border border-dashed bg-emerald-50/40 p-8 text-center">
            <div className="text-lg font-semibold text-emerald-700">
              ✓ 의심 브랜드 없음
            </div>
            <div className="mt-1 text-sm text-emerald-600/70">
              현재 적재된 모든 브랜드가 매핑됐거나 신뢰할 수 있는 추정입니다.
            </div>
          </div>
        )}

        {/* Critical */}
        {critical.length > 0 && (
          <section>
            <h2 className="mb-3 text-xl font-semibold text-red-700">
              🚨 긴급 정정 ({critical.length}개)
            </h2>
            <BrandList items={critical} />
          </section>
        )}

        {/* Warnings */}
        {warnings.length > 0 && (
          <section>
            <h2 className="mb-3 text-xl font-semibold text-amber-700">
              ⚠️ 검토 필요 ({warnings.length}개)
            </h2>
            <BrandList items={warnings} />
          </section>
        )}

        {/* Tip */}
        <div className="rounded-xl border bg-muted/30 p-4 text-sm text-muted-foreground">
          💡 정정이 필요한 케이스를 발견하시면 <code className="rounded bg-background px-1.5 py-0.5 font-mono text-xs">URL → 정확한 브랜드명</code>{" "}
          형태로 알려주세요. <code className="rounded bg-background px-1.5 py-0.5 font-mono text-xs">canonical_brand.py</code>의{" "}
          <code className="rounded bg-background px-1.5 py-0.5 font-mono text-xs">HOST_TO_BRAND</code>에 매핑을 추가하고 DB도 함께 정정해드립니다.
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
    warning: "border-amber-200 bg-amber-50/50",
    neutral: "border-border bg-card",
  };
  const numColors = {
    critical: "text-red-700",
    warning: "text-amber-700",
    neutral: "text-foreground",
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

function BrandList({ items }: { items: Awaited<ReturnType<typeof getSuspectBrands>> }) {
  return (
    <div className="space-y-3">
      {items.map((b) => {
        const url = urlFor(b.businessName, b.hostBroken);
        return (
          <div
            key={b.brandId}
            className="rounded-xl border bg-card p-5 shadow-sm"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="text-xl font-bold">
                  {b.displayName}
                </div>
                <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-mono text-muted-foreground">
                  id {b.brandId}
                </span>
                <span className="text-xs text-muted-foreground">
                  {b.usesCount}회 사용
                </span>
              </div>
              <div className="flex flex-wrap gap-1">
                {b.reasons.map((r) => reasonBadge(r))}
              </div>
            </div>

            <div className="mt-3 space-y-1.5 text-sm">
              <div className="flex items-center gap-2">
                <span className="w-16 shrink-0 text-xs text-muted-foreground">URL</span>
                {url ? (
                  <a
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 font-mono text-sm text-primary underline-offset-2 hover:underline"
                  >
                    {url}
                    <ExternalLink className="h-3 w-3" />
                  </a>
                ) : (
                  <span className="font-mono text-sm text-red-600">
                    ⚠ {b.businessName}
                  </span>
                )}
              </div>

              {b.contexts.length > 0 && (
                <div className="flex items-start gap-2">
                  <span className="w-16 shrink-0 text-xs text-muted-foreground pt-0.5">키워드</span>
                  <div className="flex flex-wrap gap-1.5">
                    {b.contexts.map((c, i) => (
                      <span
                        key={i}
                        className="inline-flex items-center gap-1 rounded bg-muted/60 px-2 py-0.5 text-xs"
                      >
                        <span className="text-muted-foreground">
                          {PRODUCT_LABEL[c.product] ?? c.product}
                        </span>
                        <span className="font-medium">{c.keywordGroup}</span>
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {b.ad_copies.length > 0 && (
                <div className="flex items-start gap-2">
                  <span className="w-16 shrink-0 text-xs text-muted-foreground pt-0.5">광고카피</span>
                  <div className="flex flex-col gap-0.5">
                    {b.ad_copies.map((c, i) => (
                      <span key={i} className="text-sm">{c}</span>
                    ))}
                  </div>
                </div>
              )}

              {b.subTitles.length > 0 && (
                <div className="flex items-start gap-2">
                  <span className="w-16 shrink-0 text-xs text-muted-foreground pt-0.5">서브타이틀</span>
                  <div className="flex flex-col gap-0.5">
                    {b.subTitles.map((c, i) => (
                      <span key={i} className="text-sm text-accent">{c}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
