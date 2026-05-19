import { config as loadEnv } from "dotenv";
loadEnv({ path: ".env.local" });

import { createDb } from "@/lib/db/client";
import { products } from "@/lib/db/schema";

async function main() {
  const db = createDb();

  await db
    .insert(products)
    .values([
      { code: "SEARCHING_VIEW", name: "서칭뷰", maxBrandsPerGroup: 1 },
      { code: "NEW_PRODUCT", name: "신제품검색", maxBrandsPerGroup: 2 },
    ])
    .onConflictDoNothing({ target: products.code });

  const rows = await db.select().from(products);
  console.log(`products in DB (${rows.length}):`);
  for (const r of rows) console.log(`  ${r.code} (max ${r.maxBrandsPerGroup} brands)`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
