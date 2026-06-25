import { config as loadEnv } from "dotenv";
loadEnv({ path: ".env.local" });

import { eq } from "drizzle-orm";
import { createDb } from "@/lib/db/client";
import { strategyParams } from "@/lib/db/schema";
import {
  getActiveStrategyParams,
  getPendingStrategyParams,
  getStrategyHistory,
  activateStrategyParams,
} from "@/lib/db/strategy-params";

async function main() {
  const db = createDb();

  console.log("== getActiveStrategyParams ==");
  const active = await getActiveStrategyParams(db);
  console.log(`  rows: ${active.length}`);
  for (const r of active) {
    console.log(
      `  - id=${r.id}  ${r.productCode}  weights=${JSON.stringify(r.weights)}`,
    );
  }
  if (active.length !== 3) {
    throw new Error(`Expected 3 active rows, got ${active.length}`);
  }
  console.log("  OK 3 active rows");

  console.log("\n== getPendingStrategyParams ==");
  const pending = await getPendingStrategyParams(db);
  console.log(`  rows: ${pending.length} (expected 0)`);
  if (pending.length !== 0) {
    throw new Error(`Expected 0 pending rows, got ${pending.length}`);
  }
  console.log("  OK no pending rows");

  console.log("\n== getStrategyHistory(SEARCHING_VIEW) ==");
  const history = await getStrategyHistory(db, "SEARCHING_VIEW");
  console.log(`  rows: ${history.length} (expected >= 1)`);
  if (history.length < 1) {
    throw new Error("Expected at least 1 history row for SEARCHING_VIEW");
  }
  console.log("  OK history rows present");

  console.log("\n== activateStrategyParams (round-trip) ==");

  // The seed active row for SEARCHING_VIEW must be id=1 (per T2 notes).
  const seedActive = active.find((r) => r.productCode === "SEARCHING_VIEW");
  if (!seedActive) throw new Error("No active SEARCHING_VIEW row to test with");
  const seedId = seedActive.id;
  console.log(`  seed active SV id=${seedId}`);

  // 1. Insert synthetic pending row
  const [inserted] = await db
    .insert(strategyParams)
    .values({
      productCode: "SEARCHING_VIEW",
      status: "pending",
      weights: [5, 3, 2, 1],
      lowPercentileBps: 3100,
      highPercentileBps: 8000,
      lowPremiumBps: 10000,
      highPremiumBps: 12000,
      expectedCostPercentileBps: null,
      deltaMaxBps: 100,
      source: "test",
      note: "verify-strategy-params synthetic",
    })
    .returning();
  console.log(`  inserted synthetic pending id=${inserted.id}`);

  try {
    // 2. Activate it
    await activateStrategyParams(db, inserted.id, "verify-strategy-params");

    // 3. Verify synthetic is now active for SV
    const afterActive = await getActiveStrategyParams(db);
    const svActive = afterActive.find((r) => r.productCode === "SEARCHING_VIEW");
    if (!svActive || svActive.id !== inserted.id) {
      throw new Error(
        `Expected synthetic id=${inserted.id} to be active SV, got id=${svActive?.id}`,
      );
    }
    if (svActive.activatedBy !== "verify-strategy-params") {
      throw new Error(
        `Expected activatedBy='verify-strategy-params', got '${svActive.activatedBy}'`,
      );
    }
    if (svActive.activatedAt == null) {
      throw new Error("Expected activatedAt to be stamped");
    }
    console.log(`  OK synthetic now active (id=${inserted.id})`);

    // 4. Verify previous seed row is archived
    const [seedRowNow] = await db
      .select()
      .from(strategyParams)
      .where(eq(strategyParams.id, seedId));
    if (seedRowNow.status !== "archived") {
      throw new Error(
        `Expected seed id=${seedId} archived, got status=${seedRowNow.status}`,
      );
    }
    console.log(`  OK seed id=${seedId} now archived`);

    // 5. Restore: re-activate the original seed row
    await activateStrategyParams(db, seedId, "verify-strategy-params-restore");
    const restored = await getActiveStrategyParams(db);
    const svRestored = restored.find((r) => r.productCode === "SEARCHING_VIEW");
    if (!svRestored || svRestored.id !== seedId) {
      throw new Error(
        `Restore failed: expected SV active id=${seedId}, got id=${svRestored?.id}`,
      );
    }
    console.log(`  OK restored: SV active id=${seedId}`);
  } finally {
    // 6. Delete synthetic row (whether it's archived or in some other state)
    await db.delete(strategyParams).where(eq(strategyParams.id, inserted.id));
    console.log(`  cleanup: deleted synthetic id=${inserted.id}`);
  }

  // 7. Final state check
  const finalActive = await getActiveStrategyParams(db);
  if (finalActive.length !== 3) {
    throw new Error(
      `Final state corrupted: expected 3 active rows, got ${finalActive.length}`,
    );
  }
  const finalPending = await getPendingStrategyParams(db);
  if (finalPending.length !== 0) {
    throw new Error(
      `Final state corrupted: expected 0 pending rows, got ${finalPending.length}`,
    );
  }
  console.log(`\n  OK final state restored (3 active, 0 pending)`);

  console.log("\nAll checks passed.");
  process.exit(0);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
