import { pgTable, serial, varchar, smallint, timestamp, uniqueIndex } from "drizzle-orm/pg-core";

export const products = pgTable(
  "products",
  {
    id: serial("id").primaryKey(),
    code: varchar("code", { length: 32 }).notNull(),
    name: varchar("name", { length: 64 }).notNull(),
    maxBrandsPerGroup: smallint("max_brands_per_group").notNull(),
    createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
  },
  (t) => ({
    codeUq: uniqueIndex("products_code_uq").on(t.code),
  })
);

export type Product = typeof products.$inferSelect;
export type NewProduct = typeof products.$inferInsert;
