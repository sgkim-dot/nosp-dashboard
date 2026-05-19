import { pgTable, serial, integer, varchar, uniqueIndex } from "drizzle-orm/pg-core";
import { roundKeywordGroups } from "./round_keyword_groups";

export const roundKeywords = pgTable(
  "round_keywords",
  {
    id: serial("id").primaryKey(),
    roundKeywordGroupId: integer("round_keyword_group_id")
      .notNull()
      .references(() => roundKeywordGroups.id, { onDelete: "cascade" }),
    keyword: varchar("keyword", { length: 128 }).notNull(),
  },
  (t) => ({
    rkgKeywordUq: uniqueIndex("round_keywords_rkg_keyword_uq").on(t.roundKeywordGroupId, t.keyword),
  })
);

export type RoundKeyword = typeof roundKeywords.$inferSelect;
export type NewRoundKeyword = typeof roundKeywords.$inferInsert;
