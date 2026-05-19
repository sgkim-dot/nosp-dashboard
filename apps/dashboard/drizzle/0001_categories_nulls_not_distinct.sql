DROP INDEX IF EXISTS "categories_parent_name_uq";
CREATE UNIQUE INDEX "categories_parent_name_uq" ON "categories" ("parent_id", "name") NULLS NOT DISTINCT;