"use server";

import { clerkClient } from "@clerk/nextjs/server";
import { revalidatePath } from "next/cache";
import { requireAdmin } from "@/lib/admin";

export async function updateMemoAction(userId: string, memo: string): Promise<void> {
  await requireAdmin();
  const client = await clerkClient();
  const trimmed = memo.trim();
  await client.users.updateUserMetadata(userId, {
    publicMetadata: { memo: trimmed.length === 0 ? null : trimmed },
  });
  revalidatePath("/users");
}

export async function banUserAction(userId: string): Promise<void> {
  await requireAdmin();
  const client = await clerkClient();
  await client.users.banUser(userId);
  revalidatePath("/users");
}

export async function unbanUserAction(userId: string): Promise<void> {
  await requireAdmin();
  const client = await clerkClient();
  await client.users.unbanUser(userId);
  revalidatePath("/users");
}
