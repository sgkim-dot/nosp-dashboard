import { getCrawlProgress } from "@/lib/db/queries";
import { CrawlAutoRefresh } from "@/components/crawl/auto-refresh";
import {
  Activity,
  CheckCircle2,
  Clock,
  Gauge,
  Timer,
  XCircle,
} from "lucide-react";

export const dynamic = "force-dynamic";

function secondsAgo(isoStr: string | null): number | null {
  if (!isoStr) return null;
  // isoStr from Postgres includes timezone; Date parses it OK
  const t = new Date(isoStr).getTime();
  if (Number.isNaN(t)) return null;
  return Math.max(0, Math.round((Date.now() - t) / 1000));
}

function fmtAgo(sec: number | null): string {
  if (sec == null) return "-";
  if (sec < 60) return `${sec}초 전`;
  if (sec < 3600) return `${Math.round(sec / 60)}분 전`;
  return `${(sec / 3600).toFixed(1)}시간 전`;
}

function fmtEta(hours: number | null): string {
  if (hours == null) return "-";
  if (hours < 1) return `${Math.round(hours * 60)}분`;
  if (hours < 24) return `${hours.toFixed(1)}시간`;
  return `${(hours / 24).toFixed(1)}일`;
}

function statusBadge(status: string | null) {
  if (status === "running") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 text-sm font-semibold text-emerald-700 ring-1 ring-emerald-200">
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75"></span>
          <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500"></span>
        </span>
        실행 중
      </span>
    );
  }
  if (status === "completed") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-3 py-1 text-sm font-medium text-blue-700 ring-1 ring-blue-200">
        <CheckCircle2 className="h-3.5 w-3.5" /> 완료
      </span>
    );
  }
  if (status === "failed") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-red-50 px-3 py-1 text-sm font-medium text-red-700 ring-1 ring-red-200">
        <XCircle className="h-3.5 w-3.5" /> 실패
      </span>
    );
  }
  if (status === "interrupted") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-3 py-1 text-sm font-medium text-amber-700 ring-1 ring-amber-200">
        <XCircle className="h-3.5 w-3.5" /> 중단됨
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-muted px-3 py-1 text-sm text-muted-foreground ring-1 ring-border">
      {status ?? "기록 없음"}
    </span>
  );
}

const MODE_LABEL: Record<string, string> = {
  resume: "이어 진행 (24h skip)",
  full: "전체 재스크랩",
  "null-only": "NULL만 처리",
  default: "기본",
};

export default async function CrawlPage() {
  const p = await getCrawlProgress();
  const overallPct =
    p.totals.total > 0 ? Math.round((p.totals.done * 100) / p.totals.total) : 0;
  const lastKgSec = secondsAgo(p.lastKgScrapedAt);
  // "actively running" heuristic: KG processed in last 5 min
  const isLive = lastKgSec != null && lastKgSec < 300;
  // Current cycle = most recent ingest_run row
  const currentCycle = p.cycles[p.cycles.length - 1] ?? null;

  return (
    <div>
      <header className="border-b bg-card px-8 py-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">크롤링 진행률</h1>
            <p className="mt-1 text-base text-muted-foreground">
              브랜드 스크래핑 BAT의 실시간 진행 상황입니다.
            </p>
          </div>
          <CrawlAutoRefresh intervalSec={30} />
        </div>
      </header>

      <div className="space-y-6 px-8 py-6">
        {/* Hero progress bar — scoped to the CURRENT cycle */}
        <div className="rounded-2xl border bg-card p-7 shadow-sm">
          <div className="flex items-center justify-between gap-6">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-base font-medium text-muted-foreground">
                  현재 사이클 진행률
                </span>
                {currentCycle && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-semibold text-primary">
                    {currentCycle.cycleNo}차 ·{" "}
                    {MODE_LABEL[currentCycle.mode] ?? currentCycle.mode}
                  </span>
                )}
                {statusBadge(isLive ? "running" : p.currentRunStatus)}
              </div>
              <div className="mt-2 text-5xl font-bold tabular-nums">
                {overallPct}%
              </div>
              <div className="mt-1 text-base text-muted-foreground tabular-nums">
                {p.totals.done.toLocaleString()} / {p.totals.total.toLocaleString()} KG ·
                {" "}남은 {p.totals.pending.toLocaleString()}개
              </div>
            </div>
            <div className="text-right">
              <div className="text-sm text-muted-foreground">예상 잔여 시간</div>
              <div className="mt-1 text-3xl font-bold tabular-nums">
                {fmtEta(p.etaHours)}
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                최근 15분 페이스 기준
              </div>
            </div>
          </div>
          {/* Progress bar */}
          <div className="mt-6 h-4 w-full overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary transition-all"
              style={{ width: `${overallPct}%` }}
            />
          </div>
        </div>

        {/* Per-product cards */}
        <div className="grid gap-4 sm:grid-cols-2">
          {p.perProduct.map((prod) => {
            const pct = prod.total > 0 ? Math.round((prod.done * 100) / prod.total) : 0;
            const brandPct = prod.done > 0 ? Math.round((prod.withBrand * 100) / prod.done) : 0;
            return (
              <div
                key={prod.productCode}
                className="rounded-xl border bg-card p-5 shadow-sm"
              >
                <div className="flex items-center justify-between">
                  <div className="text-lg font-semibold">
                    {prod.productCode === "SEARCHING_VIEW" ? "서칭뷰 (SV)" : "신제품검색 (NP)"}
                  </div>
                  <span className="rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
                    {pct}%
                  </span>
                </div>
                <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-accent transition-all"
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <div className="mt-4 grid grid-cols-3 gap-3 text-sm">
                  <Stat label="처리 완료" value={prod.done.toLocaleString()} />
                  <Stat label="남음" value={prod.pending.toLocaleString()} accent={prod.pending > 0 ? "warn" : undefined} />
                  <Stat label="광고 잡힘" value={`${prod.withBrand} (${brandPct}%)`} />
                </div>
              </div>
            );
          })}
        </div>

        {/* Cycle breakdown — simple status row (이번 BAT 실행의 1/2/3차 사이클 상태) */}
        {p.cycles.length > 0 && (
          <div className="rounded-xl border bg-card px-5 py-4">
            <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
              <span className="text-sm font-medium text-muted-foreground">
                사이클 진행
              </span>
              {[1, 2, 3].map((no) => {
                const c = p.cycles.find((x) => x.cycleNo === no);
                const isCurrent = c?.runId === currentCycle?.runId;
                const isLiveCycle = c?.status === "started" && !c?.completedAt && isCurrent;
                let label = "대기";
                let className = "bg-muted text-muted-foreground";
                if (c) {
                  if (isLiveCycle) {
                    label = "진행 중";
                    className = "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200";
                  } else if (c.status === "completed") {
                    label = "완료";
                    className = "bg-blue-50 text-blue-700 ring-1 ring-blue-200";
                  } else if (c.status === "failed" || c.status === "interrupted") {
                    label = c.status === "failed" ? "실패" : "중단";
                    className = "bg-amber-50 text-amber-700 ring-1 ring-amber-200";
                  }
                }
                return (
                  <span key={no} className="inline-flex items-center gap-1.5 text-sm">
                    <span className="text-muted-foreground">{no}차</span>
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${className}`}>
                      {label}
                    </span>
                  </span>
                );
              })}
            </div>
          </div>
        )}

        {/* Live stats grid */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <LiveStat
            icon={<Activity className="h-5 w-5" />}
            iconClass="bg-emerald-50 text-emerald-600"
            label="최근 5분 처리"
            value={`${p.rateLast5Min}개`}
            sub={`= ${p.rateLast5Min * 12}/h`}
          />
          <LiveStat
            icon={<Gauge className="h-5 w-5" />}
            iconClass="bg-blue-50 text-blue-600"
            label="최근 15분 처리"
            value={`${p.rateLast15Min}개`}
            sub={`= ${p.rateLast15Min * 4}/h`}
          />
          <LiveStat
            icon={<Timer className="h-5 w-5" />}
            iconClass="bg-amber-50 text-amber-600"
            label="최근 1시간 처리"
            value={`${p.rateLast1Hour}개`}
            sub="시간당 페이스"
          />
          <LiveStat
            icon={<Clock className="h-5 w-5" />}
            iconClass="bg-primary/10 text-primary"
            label="마지막 KG 처리"
            value={fmtAgo(lastKgSec)}
            sub={isLive ? "🟢 활발히 진행 중" : "⏸ 일시 정지/종료 추정"}
          />
        </div>

        {/* Tip */}
        <div className="rounded-xl border bg-muted/30 p-4 text-sm text-muted-foreground">
          💡 마지막 처리가 5분 이상 멈춰있으면 BAT가 종료됐거나 일시 멈춤 상태일 수
          있어요. 그럴 땐 cmd 창을 확인하고 필요 시 <code className="rounded bg-background px-1.5 py-0.5 font-mono text-xs">브랜드크롤링.bat</code> 을 다시 실행하세요 — 이어서 진행됩니다.
        </div>
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: "warn";
}) {
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div
        className={`mt-0.5 text-base font-semibold tabular-nums ${
          accent === "warn" ? "text-amber-600" : ""
        }`}
      >
        {value}
      </div>
    </div>
  );
}

function LiveStat({
  icon,
  iconClass,
  label,
  value,
  sub,
}: {
  icon: React.ReactNode;
  iconClass: string;
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="rounded-xl border bg-card p-5 shadow-sm">
      <div className="flex items-center gap-2.5">
        <span className={`grid h-9 w-9 place-items-center rounded-lg ${iconClass}`}>
          {icon}
        </span>
        <span className="text-sm font-medium text-muted-foreground">{label}</span>
      </div>
      <div className="mt-3 text-2xl font-bold tabular-nums">{value}</div>
      {sub && <div className="mt-1 text-xs text-muted-foreground">{sub}</div>}
    </div>
  );
}
