import { clerkClient } from "@clerk/nextjs/server";
import { requireAdmin } from "@/lib/admin";
import { UsersTable, type UserRow } from "@/components/users/users-table";

export const dynamic = "force-dynamic";

function toIsoOrNull(ms: number | null | undefined): string | null {
  if (ms == null) return null;
  return new Date(ms).toISOString();
}

export default async function UsersPage() {
  await requireAdmin();

  const client = await clerkClient();
  const result = await client.users.getUserList({
    limit: 100,
    orderBy: "-created_at",
  });

  const users: UserRow[] = result.data.map((u) => {
    const memo = typeof u.publicMetadata?.memo === "string" ? u.publicMetadata.memo : "";
    const name = [u.firstName, u.lastName].filter(Boolean).join(" ").trim();
    return {
      id: u.id,
      email: u.emailAddresses[0]?.emailAddress ?? "(이메일 없음)",
      name,
      imageUrl: u.imageUrl,
      createdAt: toIsoOrNull(u.createdAt) ?? "",
      lastSignInAt: toIsoOrNull(u.lastSignInAt),
      banned: u.banned,
      memo,
    };
  });

  return (
    <div>
      <header className="border-b bg-card px-8 py-6">
        <h1 className="text-3xl font-bold tracking-tight">사용자 관리</h1>
        <p className="mt-1 text-base text-muted-foreground">
          현재 가입된 사용자 {users.length}명. 메모를 추가하거나 접속을 차단/해제할 수 있습니다.
        </p>
      </header>
      <div className="px-6 py-4">
        <UsersTable users={users} />
      </div>
    </div>
  );
}
