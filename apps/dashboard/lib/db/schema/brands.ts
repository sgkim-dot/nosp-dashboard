import { pgTable, serial, varchar, jsonb, timestamp, uniqueIndex } from "drizzle-orm/pg-core";

export const brands = pgTable(
  "brands",
  {
    id: serial("id").primaryKey(),
    businessName: varchar("business_name", { length: 256 }).notNull(),
    displayName: varchar("display_name", { length: 128 }).notNull(),
    aliases: jsonb("aliases").$type<string[]>().notNull().default([]),
    createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
  },
  (t) => ({
    businessUq: uniqueIndex("brands_business_uq").on(t.businessName),
  })
);

export type Brand = typeof brands.$inferSelect;
export type NewBrand = typeof brands.$inferInsert;
