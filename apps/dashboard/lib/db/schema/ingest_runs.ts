import { pgTable, serial, integer, varchar, text, timestamp } from "drizzle-orm/pg-core";
import { products } from "./products";

export const ingestRuns = pgTable("ingest_runs", {
  id: serial("id").primaryKey(),
  runType: varchar("run_type", { length: 32 }).notNull(),
  productId: integer("product_id").references(() => products.id),
  filePath: text("file_path"),
  status: varchar("status", { length: 16 }).notNull(),
  errorMessage: text("error_message"),
  rowsTotal: integer("rows_total"),
  rowsInserted: integer("rows_inserted"),
  rowsUpdated: integer("rows_updated"),
  runAt: timestamp("run_at", { withTimezone: true }).defaultNow().notNull(),
  completedAt: timestamp("completed_at", { withTimezone: true }),
});

export type IngestRun = typeof ingestRuns.$inferSelect;
export type NewIngestRun = typeof ingestRuns.$inferInsert;
