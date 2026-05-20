import "server-only";
import { asc, eq, sql } from "drizzle-orm";
import { createDb } from "./client";
import { categories, products } from "./schema";
import type {
  Insights,
  KeywordGroupSummary,
  ProductCode,
  RoundBrand,
  RoundRow,
} from "@/types/bid-decision";

const db = createDb();

export async function getProducts() {
  return db.select().from(products).orderBy(asc(products.id));
}

export async function getCategoriesLvl1() {
  const rows = await db
    .select({ id: categories.id, name: categories.name })
    .from(categories)
    .where(eq(categories.level, 1))
    .orderBy(asc(categories.name));
  return rows;
}

export async function getCategoriesLvl2(lvl1Name: string) {
  const result = await db.execute<{ id: number; name: string }>(sql`
    SELECT c2.id, c2.name
    FROM categories c1
    JOIN categories c2 ON c2.parent_id = c1.id AND c2.level = 2
    WHERE c1.level = 1 AND c1.name = ${lvl1Name}
    ORDER BY c2.name
  `);
  return result.rows;
}

export async function getKeywordGroups(args: {
  product: ProductCode;
  categoryLvl1: string | null;
  categoryLvl2: string | null;
}) {
  const result = await db.execute<{ id: number; name: string }>(sql`
    SELECT kg.id, kg.name
    FROM keyword_groups kg
    JOIN products p ON p.id = kg.product_id
    JOIN categories c2 ON c2.id = kg.category_id
    JOIN categories c1 ON c1.id = c2.parent_id
    WHERE p.code = ${args.product}
      ${args.categoryLvl1 ? sql`AND c1.name = ${args.categoryLvl1}` : sql``}
      ${args.categoryLvl2 ? sql`AND c2.name = ${args.categoryLvl2}` : sql``}
    ORDER BY kg.name
    LIMIT 500
  `);
  return result.rows;
}

type HeadRow = {
  keyword_group_id: number;
  keyword_group_name: string;
  product: ProductCode;
  category_lvl1: string;
  category_lvl2: string;
};

type TailRow = {
  round_id: number;
  round_no: number;
  period_start: string;
  period_end: string;
  min_bid_price: number | null;
  regular_winning_bid: number | null;
  empty_slots: number | null;
  bid_status: string | null;
};

export async function getKeywordGroupSummary(args: {
  keywordGroupId: number;
  lastNRounds: number;
}): Promise<KeywordGroupSummary | null> {
  const head = await db.execute<HeadRow>(sql`
    SELECT
      kg.id AS keyword_group_id,
      kg.name AS keyword_group_name,
      p.code AS product,
      c1.name AS category_lvl1,
      c2.name AS category_lvl2
    FROM keyword_groups kg
    JOIN products p ON p.id = kg.product_id
    JOIN categories c2 ON c2.id = kg.category_id
    JOIN categories c1 ON c1.id = c2.parent_id
    WHERE kg.id = ${args.keywordGroupId}
  `);

  if (head.rows.length === 0) return null;
  const h = head.rows[0];

  const tail = await db.execute<TailRow>(sql`
    SELECT
      r.id AS round_id,
      r.round_no,
      r.period_start::text AS period_start,
      r.period_end::text AS period_end,
      rkg.min_bid_price,
      rkg.regular_winning_bid,
      rkg.empty_slots,
      rkg.bid_status
    FROM round_keyword_groups rkg
    JOIN rounds r ON r.id = rkg.round_id
    WHERE rkg.keyword_group_id = ${args.keywordGroupId}
    ORDER BY r.round_no DESC
    LIMIT ${args.lastNRounds}
  `);

  const brandsResult = await db.execute<{
    round_id: number;
    slot_no: number;
    display_name: string;
    business_name: string;
    source: string;
    confidence: number | null;
  }>(sql`
    SELECT
      rkg.round_id,
      rb.slot_no,
      b.display_name,
      b.business_name,
      rb.source,
      rb.confidence
    FROM round_brands rb
    JOIN round_keyword_groups rkg ON rkg.id = rb.round_keyword_group_id
    JOIN brands b ON b.id = rb.brand_id
    WHERE rkg.keyword_group_id = ${args.keywordGroupId}
    ORDER BY rb.slot_no
  `);

  const brandsByRound = new Map<number, RoundBrand[]>();
  for (const r of brandsResult.rows) {
    const list = brandsByRound.get(r.round_id) ?? [];
    list.push({
      slotNo: r.slot_no,
      displayName: r.display_name,
      businessName: r.business_name,
      source: r.source as RoundBrand["source"],
      confidence: r.confidence,
    });
    brandsByRound.set(r.round_id, list);
  }

  const roundsAsc: RoundRow[] = tail.rows
    .slice()
    .reverse()
    .map((r) => ({
      roundId: r.round_id,
      roundNo: r.round_no,
      periodStart: r.period_start,
      periodEnd: r.period_end,
      minBidPrice: r.min_bid_price,
      regularWinningBid: r.regular_winning_bid,
      emptySlots: r.empty_slots,
      bidStatus: r.bid_status,
      ratio:
        r.regular_winning_bid != null && r.min_bid_price
          ? r.regular_winning_bid / r.min_bid_price
          : null,
      brands: brandsByRound.get(r.round_id) ?? [],
    }));

  const latestRound = roundsAsc[roundsAsc.length - 1];
  const lastAnnounced = [...roundsAsc]
    .reverse()
    .find((r) => r.regularWinningBid != null);
  return {
    keywordGroupId: h.keyword_group_id,
    keywordGroupName: h.keyword_group_name,
    product: h.product,
    categoryLvl1: h.category_lvl1,
    categoryLvl2: h.category_lvl2,
    latestWinning: lastAnnounced?.regularWinningBid ?? null,
    latestEmptySlots: latestRound?.emptySlots ?? null,
    latestBrands: latestRound?.brands ?? [],
    rounds: roundsAsc,
  };
}

export type HeatmapCell = {
  brandId: number;
  brandDisplayName: string;
  roundNo: number;
  keywordGroupName: string;
  slotNo: number;
};

export async function getBrandHeatmap(args: {
  product: ProductCode;
  categoryLvl1: string | null;
  lastNRounds: number;
}): Promise<HeatmapCell[]> {
  const result = await db.execute<{
    brand_id: number;
    display_name: string;
    round_no: number;
    keyword_group_name: string;
    slot_no: number;
  }>(sql`
    WITH recent_rounds AS (
      SELECT r.id, r.round_no
      FROM rounds r
      JOIN products p ON p.id = r.product_id
      WHERE p.code = ${args.product}
      ORDER BY r.round_no DESC
      LIMIT ${args.lastNRounds}
    )
    SELECT
      b.id AS brand_id,
      b.display_name,
      r.round_no,
      kg.name AS keyword_group_name,
      rb.slot_no
    FROM round_brands rb
    JOIN round_keyword_groups rkg ON rkg.id = rb.round_keyword_group_id
    JOIN recent_rounds r ON r.id = rkg.round_id
    JOIN keyword_groups kg ON kg.id = rkg.keyword_group_id
    JOIN categories c2 ON c2.id = kg.category_id
    JOIN categories c1 ON c1.id = c2.parent_id
    JOIN brands b ON b.id = rb.brand_id
    WHERE 1=1
      ${args.categoryLvl1 ? sql`AND c1.name = ${args.categoryLvl1}` : sql``}
    ORDER BY b.display_name, r.round_no DESC
  `);
  return result.rows.map((r) => ({
    brandId: r.brand_id,
    brandDisplayName: r.display_name,
    roundNo: r.round_no,
    keywordGroupName: r.keyword_group_name,
    slotNo: r.slot_no,
  }));
}

export function computeInsights(summary: KeywordGroupSummary): Insights {
  const ratios = summary.rounds
    .map((r) => r.ratio)
    .filter((r): r is number => r != null);
  const vacancies = summary.rounds.filter((r) => (r.emptySlots ?? 0) > 0).length;
  const latestMin =
    summary.rounds[summary.rounds.length - 1]?.minBidPrice ?? null;

  if (ratios.length === 0) {
    return {
      meanRatio: null,
      vacancyRate:
        summary.rounds.length === 0 ? null : vacancies / summary.rounds.length,
      recommendedLow: null,
      recommendedHigh: null,
    };
  }

  const sorted = [...ratios].sort((a, b) => a - b);
  const p20 = sorted[Math.floor(sorted.length * 0.2)] ?? sorted[0];
  const p80 =
    sorted[Math.floor(sorted.length * 0.8)] ?? sorted[sorted.length - 1];
  const mean = ratios.reduce((a, b) => a + b, 0) / ratios.length;

  return {
    meanRatio: mean,
    vacancyRate: vacancies / summary.rounds.length,
    recommendedLow: latestMin
      ? Math.round((latestMin * p20) / 1000) * 1000
      : null,
    recommendedHigh: latestMin
      ? Math.round((latestMin * p80) / 1000) * 1000
      : null,
  };
}
