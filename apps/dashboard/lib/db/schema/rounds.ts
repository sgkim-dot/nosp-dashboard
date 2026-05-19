import { pgTable, serial, integer, date, uniqueIndex } from "drizzle-orm/pg-core";
import { products } from "./products";

export const rounds = pgTable(
  "rounds",
  {
    id: serial("id").primaryKey(),
    productId: integer("product_id").notNull().references(() => products.id),
    roundNo: integer("round_no").notNull(), // e.g. 202624
    periodStart: date("period_start").notNull(),
    periodEnd: date("period_end").notNull(),
    regularBidStart: date("regular_bid_start"),
    regularBidEnd: date("regular_bid_end"),
    regularAnnounceDate: date("regular_announce_date"),
    rebidStart: date("rebid_start"),
    rebidEnd: date("rebid_end"),
    rebidAnnounceDate: date("rebid_announce_date"),
  },
  (t) => ({
    productRoundUq: uniqueIndex("rounds_product_round_uq").on(t.productId, t.roundNo),
  })
);

export type Round = typeof rounds.$inferSelect;
export type NewRound = typeof rounds.$inferInsert;
