"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { RefreshCw } from "lucide-react";

/**
 * Tiny client widget that triggers router.refresh() on a fixed interval and
 * shows seconds-until-next-refresh. The actual data is fetched server-side
 * (queries.ts), so the page itself stays a Server Component.
 */
export function CrawlAutoRefresh({ intervalSec = 30 }: { intervalSec?: number }) {
  const router = useRouter();
  const [secs, setSecs] = useState(intervalSec);
  const [refreshing, setRefreshing] = useState(false);
  const secsRef = useRef(intervalSec);

  useEffect(() => {
    secsRef.current = intervalSec;
    setSecs(intervalSec);
    const tick = setInterval(() => {
      if (secsRef.current <= 1) {
        secsRef.current = intervalSec;
        setSecs(intervalSec);
        setRefreshing(true);
        router.refresh();
        setTimeout(() => setRefreshing(false), 400);
      } else {
        secsRef.current -= 1;
        setSecs(secsRef.current);
      }
    }, 1000);
    return () => clearInterval(tick);
  }, [intervalSec, router]);

  return (
    <button
      type="button"
      onClick={() => {
        secsRef.current = intervalSec;
        setSecs(intervalSec);
        setRefreshing(true);
        router.refresh();
        setTimeout(() => setRefreshing(false), 400);
      }}
      className="inline-flex items-center gap-1.5 rounded-lg border bg-card px-3 py-1.5 text-sm text-muted-foreground hover:bg-muted hover:text-foreground"
      title={`${intervalSec}초마다 자동 갱신`}
    >
      <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
      {refreshing ? "갱신 중…" : `${secs}초 후 자동 갱신`}
    </button>
  );
}
