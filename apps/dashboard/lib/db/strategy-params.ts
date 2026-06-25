import { and, desc, eq } from "drizzle-orm";
import type { Db } from "./client";
import { strategyParams } from "./schema";

export type StrategyParamsRow = typeof strategyParams.$inferSelect;

export async function getActiveStrategyParams(
  db: Db,
): Promise<StrategyParamsRow[]> {
  return db
    .select()
    .from(strategyParams)
    .where(eq(strategyParams.status, "active"));
}

export async function getPendingStrategyParams(
  db: Db,
): Promise<StrategyParamsRow[]> {
  return db
    .select()
    .from(strategyParams)
    .where(eq(strategyParams.status, "pending"))
    .orderBy(desc(strategyParams.createdAt));
}

export async function getStrategyHistory(
  db: Db,
  productCode: string,
  limit = 20,
): Promise<StrategyParamsRow[]> {
  return db
    .select()
    .from(strategyParams)
    .where(eq(strategyParams.productCode, productCode))
    .orderBy(desc(strategyParams.createdAt))
    .limit(limit);
}

/**
 * Activate the given strategy_params row for its product:
 *   1. Look up the target row (and its product_code).
 *   2. UPDATE any currently-active row for that product → 'archived'.
 *   3. UPDATE the target row → 'active' + stamp activatedAt / activatedBy.
 *
 * Concurrency note: the table has a partial unique index
 * `(product_code) WHERE status = 'active'`, so step 2 MUST run before step 3
 * or the second update violates the index.
 *
 * Driver note: the Neon HTTP driver (`drizzle-orm/neon-http`) does NOT
 * support multi-statement transactions — `db.transaction()` would throw
 * `No transactions support in neon-http driver`. We therefore run the two
 * statements sequentially and, if step 3 fails, restore the previously-active
 * row so the table never ends up with zero active rows for a product.
 *
 * Caller MUST verify userId is authorized (master role) BEFORE calling.
 */
export async function activateStrategyParams(
  db: Db,
  id: number,
  userId: string,
): Promise<void> {
  const [target] = await db
    .select()
    .from(strategyParams)
    .where(eq(strategyParams.id, id));
  if (!target) {
    throw new Error(`strategy_params id=${id} not found`);
  }

  // Capture the row we're about to archive so we can restore it on failure.
  const previouslyActive = await db
    .select()
    .from(strategyParams)
    .where(
      and(
        eq(strategyParams.productCode, target.productCode),
        eq(strategyParams.status, "active"),
      ),
    );

  // Step 1: archive current active (frees the partial unique index).
  await db
    .update(strategyParams)
    .set({ status: "archived" })
    .where(
      and(
        eq(strategyParams.productCode, target.productCode),
        eq(strategyParams.status, "active"),
      ),
    );

  // Step 2: activate target. On failure, restore the archived row.
  try {
    await db
      .update(strategyParams)
      .set({
        status: "active",
        activatedAt: new Date(),
        activatedBy: userId,
      })
      .where(eq(strategyParams.id, id));
  } catch (err) {
    // Restore: re-activate whatever was active before so the product is
    // never left without an active row.
    for (const prev of previouslyActive) {
      await db
        .update(strategyParams)
        .set({ status: "active" })
        .where(eq(strategyParams.id, prev.id));
    }
    throw err;
  }
}
