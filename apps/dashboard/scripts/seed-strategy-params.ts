import { config as loadEnv } from "dotenv";
loadEnv({ path: ".env.local" });

import { and, eq } from "drizzle-orm";
import { createDb } from "@/lib/db/client";
import { strategyParams } from "@/lib/db/schema";

async function main() {
  const db = createDb();

  // Bps encoding: ratio × 10000 (e.g. 0.30 → 3000, 1.20 → 12000)
  // Seeds from strategy.ts hardcoded values (last tuned 2026-06-01).
  const now = new Date();
  const seed = [
    {
      productCode: "SEARCHING_VIEW",
      status: "active",
      weights: [5, 3, 2, 1],
      lowPercentileBps: 3000,
      highPercentileBps: 8000,
      lowPremiumBps: 10000,
      highPremiumBps: 12000,
      expectedCostPercentileBps: null,
      backtestScoreBps: 9930, // 99.3%
      sampleSize: 2966,
      avgOverpay: 163000,
      avgUnderbid: 108000,
      deltaMaxBps: 0,
      source: "seed",
      note: "strategy.ts 2026-06-01 hardcoded values (initial seed)",
      activatedAt: now,
      activatedBy: "seed",
    },
    {
      productCode: "NEW_PRODUCT",
      status: "active",
      weights: [5, 3, 2, 1],
      lowPercentileBps: 7000,
      highPercentileBps: 7000,
      lowPremiumBps: 10500,
      highPremiumBps: 13000,
      expectedCostPercentileBps: 7000,
      backtestScoreBps: 9940,
      sampleSize: 18446,
      avgOverpay: 110000,
      avgUnderbid: 530000,
      deltaMaxBps: 0,
      source: "seed",
      note: "strategy.ts 2026-06-01 hardcoded values (initial seed)",
      activatedAt: now,
      activatedBy: "seed",
    },
    {
      productCode: "ANNIVERSARY",
      status: "active",
      weights: [5, 3, 2, 1],
      lowPercentileBps: 7000,
      highPercentileBps: 7000,
      lowPremiumBps: 10500,
      highPremiumBps: 13000,
      expectedCostPercentileBps: 7000,
      backtestScoreBps: null,
      sampleSize: null,
      avgOverpay: null,
      avgUnderbid: null,
      deltaMaxBps: 0,
      source: "seed",
      note: "ANNIVERSARY uses NEW_PRODUCT params (initial seed)",
      activatedAt: now,
      activatedBy: "seed",
    },
  ];

  // Idempotent: if any active row already exists for these product_codes,
  // skip. This makes the seed safe to re-run (e.g. local dev resets).
  for (const row of seed) {
    const existing = await db
      .select({ id: strategyParams.id })
      .from(strategyParams)
      .where(
        and(
          eq(strategyParams.productCode, row.productCode),
          eq(strategyParams.status, "active"),
        ),
      )
      .limit(1);

    if (existing.length > 0) {
      console.log(
        `[seed] skip ${row.productCode}: active row exists (id=${existing[0].id})`,
      );
      continue;
    }
    await db.insert(strategyParams).values(row);
    console.log(`[seed] inserted ${row.productCode}`);
  }
  process.exit(0);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
