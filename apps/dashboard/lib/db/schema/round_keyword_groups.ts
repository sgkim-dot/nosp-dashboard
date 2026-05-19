import {
  pgTable,
  serial,
  integer,
  varchar,
  bigint,
  smallint,
  timestamp,
  uniqueIndex,
} from "drizzle-orm/pg-core";
import { rounds } from "./rounds";
import { keywordGroups } from "./keyword_groups";

export const roundKeywordGroups = pgTable(
  "round_keyword_groups",
  {
    id: serial("id").primaryKey(),
    roundId: integer("round_id").notNull().references(() => rounds.id),
    keywordGroupId: integer("keyword_group_id").notNull().references(() => keywordGroups.id),
    referenceQueryVolume: integer("reference_query_volume"),
    minBidPrice: bigint("min_bid_price", { mode: "number" }),
    bidStatus: varchar("bid_status", { length: 32 }),
    emptySlots: smallint("empty_slots"),
    keywordCount: smallint("keyword_count"),
    regularWinningBid: bigint("regular_winning_bid", { mode: "number" }),
    capturedAt: timestamp("captured_at", { withTimezone: true }),
    createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
    updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow().notNull(),
  },
  (t) => ({
    roundKgUq: uniqueIndex("round_keyword_groups_round_kg_uq").on(t.roundId, t.keywordGroupId),
  })
);

export type RoundKeywordGroup = typeof roundKeywordGroups.$inferSelect;
export type NewRoundKeywordGroup = typeof roundKeywordGroups.$inferInsert;
