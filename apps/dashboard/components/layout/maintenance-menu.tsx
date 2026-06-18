"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  Wrench,
  ChevronDown,
  BarChart3,
  Activity,
  AlertTriangle,
  AlertOctagon,
} from "lucide-react";

const MAINTENANCE_ITEMS = [
  { href: "/backtest", label: "추천가 검증", icon: BarChart3 },
  { href: "/crawl", label: "크롤링 진행률", icon: Activity },
  { href: "/brand-cleanup", label: "브랜드 정리 필요", icon: AlertTriangle },
  { href: "/scrape-misses", label: "광고 누락 의심", icon: AlertOctagon },
];

export function MaintenanceMenu() {
  const pathname = usePathname();
  const containsActive = MAINTENANCE_ITEMS.some((i) => pathname === i.href);
  // Auto-open when the current path lives inside the group.
  const [open, setOpen] = useState(containsActive);

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-base font-medium text-sidebar-foreground/85 transition hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
        aria-expanded={open}
      >
        <Wrench className="h-5 w-5 opacity-85" aria-hidden />
        <span className="flex-1 text-left">유지보수</span>
        <ChevronDown
          className={`h-4 w-4 opacity-70 transition-transform ${open ? "rotate-180" : ""}`}
          aria-hidden
        />
      </button>
      {open && (
        <div className="mt-1 ml-3 space-y-0.5 border-l border-sidebar-border/40 pl-2">
          {MAINTENANCE_ITEMS.map(({ href, label, icon: Icon }) => {
            const active = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${
                  active
                    ? "bg-sidebar-accent text-sidebar-accent-foreground"
                    : "text-sidebar-foreground/75 hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground"
                }`}
              >
                <Icon className="h-4 w-4 opacity-85" aria-hidden />
                {label}
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
