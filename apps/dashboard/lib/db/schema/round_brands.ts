import {
  pgTable,
  serial,
  integer,
  smallint,
  varchar,
  doublePrecision,
  timestamp,
  uniqueIndex,
} from "drizzle-orm/pg-core";
import { roundKeywordGroups } from "./round_keyword_groups";
import { brands } from "./brands";

export const roundBrands = pgTable(
  "round_brands",
  {
    id: serial("id").primaryKey(),
    roundKeywordGroupId: integer("round_keyword_group_id")
      .notNull()
      .references(() => roundKeywordGroups.id, { onDelete: "cascade" }),
    brandId: integer("brand_id").references(() => brands.id),
    slotNo: smallint("slot_no").notNull(),
    displayName: varchar("display_name", { length: 200 }),
    source: varchar("source", { length: 32 }).notNull(),
    confidence: doublePrecision("confidence"),
    capturedAt: timestamp("captured_at", { withTimezone: true }).defaultNow().notNull(),
  },
  (t) => ({
    rkgSlotUq: uniqueIndex("round_brands_rkg_slot_uq").on(t.roundKeywordGroupId, t.slotNo),
  })
);

export type RoundBrand = typeof roundBrands.$inferSelect;
export type NewRoundBrand = typeof roundBrands.$inferInsert;
