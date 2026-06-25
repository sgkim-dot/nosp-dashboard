"use server";

import { auth } from "@clerk/nextjs/server";
import { revalidatePath } from "next/cache";
import { tuneStrategy, type TuneResult } from "@/lib/db/queries";
import { activateStrategyParams } from "@/lib/db/strategy-params";
import { createDb } from "@/lib/db/client";
import { getIsAdmin } from "@/lib/admin";

export async function runTuneAction(): Promise<TuneResult[]> {
  return tuneStrategy({ topN: 5, minSims: 50 });
}

export async function activateStrategyAction(id: number): Promise<void> {
  const { userId } = await auth();
  if (!userId) throw new Error("로그인이 필요합니다");
  if (!(await getIsAdmin())) {
    throw new Error("관리자 권한이 필요합니다");
  }
  const db = createDb();
  await activateStrategyParams(db, id, userId);
  revalidatePath("/backtest");
}
