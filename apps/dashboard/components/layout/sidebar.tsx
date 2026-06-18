import Link from "next/link";
import { Gauge, Building2, Tag, Activity, AlertTriangle, BarChart3 } from "lucide-react";
import { UserButton } from "@clerk/nextjs";

const NAV = [
  { href: "/", label: "입낙찰 히스토리", icon: Gauge },
  { href: "/brand", label: "브랜드 점유", icon: Building2 },
  { href: "/brand-tracker", label: "브랜드 추적", icon: Tag },
  { href: "/backtest", label: "추천가 검증", icon: BarChart3 },
  { href: "/crawl", label: "크롤링 진행률", icon: Activity },
  { href: "/brand-cleanup", label: "브랜드 정리 필요", icon: AlertTriangle },
];

export function Sidebar() {
  return (
    <aside className="w-72 shrink-0 bg-sidebar text-sidebar-foreground flex flex-col">
      <div className="px-6 pt-7 pb-10">
        <div className="flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-xl bg-sidebar-primary text-sidebar-primary-foreground text-lg font-bold">
            N
          </div>
          <div>
            <div className="text-lg font-semibold tracking-tight">NOSP 입찰</div>
            <div className="text-sm text-sidebar-foreground/60">대시보드</div>
          </div>
        </div>
      </div>
      <nav className="flex-1 space-y-1 px-4">
        <div className="px-3 pb-2 text-xs font-semibold uppercase tracking-wider text-sidebar-foreground/40">
          메인
        </div>
        {NAV.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-base font-medium text-sidebar-foreground/85 transition hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
          >
            <Icon className="h-5 w-5 opacity-85" aria-hidden />
            {label}
          </Link>
        ))}
      </nav>
      <div className="border-t border-sidebar-border px-6 py-5 flex items-center justify-between">
        <UserButton
          appearance={{
            elements: { userButtonAvatarBox: "h-9 w-9" },
          }}
          showName
        />
        <span className="text-xs text-sidebar-foreground/50">© 2026 NOSP</span>
      </div>
    </aside>
  );
}
