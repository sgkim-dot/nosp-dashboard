"use server";

import { tuneStrategy, type TuneResult } from "@/lib/db/queries";

export async function runTuneAction(): Promise<TuneResult[]> {
  return tuneStrategy({ topN: 5, minSims: 50 });
}
