import { pgTable, serial, integer, varchar, smallint, uniqueIndex } from "drizzle-orm/pg-core";

export const categories = pgTable(
  "categories",
  {
    id: serial("id").primaryKey(),
    parentId: integer("parent_id"),
    name: varchar("name", { length: 128 }).notNull(),
    level: smallint("level").notNull(), // 1 = 대분류, 2 = 소분류
  },
  (t) => ({
    nameLevelUq: uniqueIndex("categories_parent_name_uq").on(t.parentId, t.name),
  })
);

export type Category = typeof categories.$inferSelect;
export type NewCategory = typeof categories.$inferInsert;
