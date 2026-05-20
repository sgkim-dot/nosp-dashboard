import Link from "next/link";
import { Gauge, Calendar, Building2, Settings2 } from "lucide-react";

const NAV = [
  { href: "/", label: "입찰 의사결정", icon: Gauge },
  { href: "/round", label: "회차 현황", icon: Calendar },
  { href: "/brand", label: "브랜드 점유", icon: Building2 },
  { href: "/ops", label: "운영", icon: Settings2 },
];

export function Sidebar() {
  return (
    <aside className="w-56 shrink-0 border-r bg-muted/30 px-3 py-4">
      <div className="px-2 pb-4">
        <div className="text-sm font-semibold tracking-tight">NOSP 입찰</div>
        <div className="text-xs text-muted-foreground">대시보드</div>
      </div>
      <nav className="space-y-1">
        {NAV.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-foreground/80 hover:bg-accent hover:text-accent-foreground"
          >
            <Icon className="h-4 w-4" aria-hidden />
            {label}
          </Link>
        ))}
      </nav>
    </aside>
  );
}
