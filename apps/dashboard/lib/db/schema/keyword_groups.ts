import { pgTable, serial, integer, varchar, uniqueIndex } from "drizzle-orm/pg-core";
import { products } from "./products";
import { categories } from "./categories";

export const keywordGroups = pgTable(
  "keyword_groups",
  {
    id: serial("id").primaryKey(),
    productId: integer("product_id").notNull().references(() => products.id),
    categoryId: integer("category_id").notNull().references(() => categories.id),
    name: varchar("name", { length: 128 }).notNull(),
    // Per-kg override for the Naver search query. NULL → fall back to `name`.
    // Display uses `name`; only worker/jobs/brand_scrape.py reads this.
    searchKeyword: varchar("search_keyword", { length: 128 }),
  },
  (t) => ({
    productNameUq: uniqueIndex("keyword_groups_product_name_uq").on(t.productId, t.name),
  })
);

export type KeywordGroup = typeof keywordGroups.$inferSelect;
export type NewKeywordGroup = typeof keywordGroups.$inferInsert;
