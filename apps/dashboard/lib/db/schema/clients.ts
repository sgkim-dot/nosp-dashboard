import { pgTable, serial, varchar, integer, jsonb, timestamp, uniqueIndex } from "drizzle-orm/pg-core";

export const clients = pgTable(
  "clients",
  {
    id: serial("id").primaryKey(),
    slug: varchar("slug", { length: 64 }).notNull(),
    displayName: varchar("display_name", { length: 128 }).notNull(),
    brandIds: jsonb("brand_ids").$type<number[]>().notNull().default([]),
    sheetId: varchar("sheet_id", { length: 128 }),
    reportConfig: jsonb("report_config").$type<Record<string, unknown>>().notNull().default({}),
    createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
  },
  (t) => ({
    slugUq: uniqueIndex("clients_slug_uq").on(t.slug),
  })
);

export type Client = typeof clients.$inferSelect;
export type NewClient = typeof clients.$inferInsert;
