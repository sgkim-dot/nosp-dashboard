import { getBrandSummaries, getBrandHistory } from "@/lib/db/queries";
import { BrandTracker } from "@/components/brand-tracker/brand-tracker";

export const dynamic = "force-dynamic";

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

function pickStr(v: string | string[] | undefined): string | null {
  if (Array.isArray(v)) return v[0] ?? null;
  return v ?? null;
}

export default async function BrandTrackerPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const sp = await searchParams;
  const brandIdRaw = pickStr(sp.brandId);
  const brandId = brandIdRaw ? Number.parseInt(brandIdRaw, 10) : null;

  const summaries = await getBrandSummaries();
  const detail =
    brandId && !Number.isNaN(brandId) ? await getBrandHistory(brandId) : null;

  return (
    <div>
      <header className="border-b px-6 py-3">
        <h1 className="text-lg font-semibold">브랜드 추적</h1>
        <p className="text-xs text-muted-foreground">
          개별 브랜드(광고주)가 어떤 회차·키워드그룹에 노출되었는지 누적 기록을 확인합니다.
        </p>
      </header>
      <BrandTracker
        brands={summaries}
        selectedBrandId={brandId}
        detail={detail}
      />
    </div>
  );
}
