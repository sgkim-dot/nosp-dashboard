import Link from "next/link";
import { Gauge, Building2, Tag } from "lucide-react";
import { UserButton } from "@clerk/nextjs";
import { currentUser } from "@clerk/nextjs/server";
import { MaintenanceMenu } from "./maintenance-menu";

// Maintenance tools are admin-only. Add admin emails here when ops scope grows.
const ADMIN_EMAILS = new Set(["sgkim@madup.com"]);

const NAV = [
  { href: "/", label: "입낙찰 히스토리", icon: Gauge },
  { href: "/brand", label: "브랜드 점유", icon: Building2 },
  { href: "/brand-tracker", label: "브랜드 추적", icon: Tag },
];

export async function Sidebar() {
  const user = await currentUser();
  const email = user?.emailAddresses?.[0]?.emailAddress ?? null;
  const isAdmin = email !== null && ADMIN_EMAILS.has(email);

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
        {isAdmin && (
          <>
            <div className="mt-6 px-3 pb-2 text-xs font-semibold uppercase tracking-wider text-sidebar-foreground/40">
              관리자
            </div>
            <MaintenanceMenu />
          </>
        )}
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
