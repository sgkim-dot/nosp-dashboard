import { sql } from "drizzle-orm";
import {
  pgTable,
  serial,
  varchar,
  timestamp,
  jsonb,
  text,
  integer,
  uniqueIndex,
} from "drizzle-orm/pg-core";

export const strategyParams = pgTable(
  "strategy_params",
  {
    id: serial("id").primaryKey(),
    productCode: varchar("product_code", { length: 32 }).notNull(),
    // 'active' | 'pending' | 'archived'
    status: varchar("status", { length: 16 }).notNull(),
    weights: jsonb("weights").$type<number[]>().notNull(),
    // basis points (0..10000) — 3000 = 0.30
    lowPercentileBps: integer("low_percentile_bps").notNull(),
    highPercentileBps: integer("high_percentile_bps").notNull(),
    // 10000 = 1.0, 12000 = 1.2
    lowPremiumBps: integer("low_premium_bps").notNull(),
    highPremiumBps: integer("high_premium_bps").notNull(),
    expectedCostPercentileBps: integer("expected_cost_percentile_bps"),
    backtestScoreBps: integer("backtest_score_bps"),
    sampleSize: integer("sample_size"),
    // KRW
    avgOverpay: integer("avg_overpay"),
    // KRW
    avgUnderbid: integer("avg_underbid"),
    // 직전 active 대비 최대 변동폭 (bps). pending 결정 근거
    deltaMaxBps: integer("delta_max_bps"),
    // 'tune_strategy.py' | 'manual' | 'seed'
    source: varchar("source", { length: 64 }).notNull(),
    note: text("note"),
    createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
    activatedAt: timestamp("activated_at", { withTimezone: true }),
    // clerk user id, or 'seed' / 'tune_strategy.py' for non-human activators
    activatedBy: varchar("activated_by", { length: 128 }),
  },
  (t) => ({
    activePerProduct: uniqueIndex("strategy_params_active_unique")
      .on(t.productCode)
      .where(sql`status = 'active'`),
  }),
);

export type StrategyParams = typeof strategyParams.$inferSelect;
export type NewStrategyParams = typeof strategyParams.$inferInsert;
