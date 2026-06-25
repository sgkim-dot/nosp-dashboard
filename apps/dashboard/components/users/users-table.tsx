"use client";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { MemoInput } from "./memo-input";
import { BanButton } from "./ban-button";

export type UserRow = {
  id: string;
  email: string;
  name: string;
  imageUrl: string;
  createdAt: string;
  lastSignInAt: string | null;
  banned: boolean;
  memo: string;
};

function fmtDate(iso: string | null): string {
  if (!iso) return "-";
  return iso.slice(0, 10);
}

function fmtDateTime(iso: string | null): string {
  if (!iso) return "-";
  return `${iso.slice(0, 10)} ${iso.slice(11, 16)}`;
}

export function UsersTable({ users }: { users: UserRow[] }) {
  if (users.length === 0) {
    return (
      <div className="rounded-md border border-dashed bg-muted/30 p-12 text-center text-sm text-muted-foreground">
        가입된 사용자가 없습니다.
      </div>
    );
  }

  return (
    <div className="rounded-xl border bg-card shadow-sm overflow-x-auto">
      <Table className="text-sm">
        <TableHeader>
          <TableRow className="[&_th]:text-sm [&_th]:font-semibold [&_th]:text-muted-foreground [&_th]:py-3 bg-muted/40">
            <TableHead className="w-[280px]">사용자</TableHead>
            <TableHead className="w-[120px]">가입일</TableHead>
            <TableHead className="w-[160px]">마지막 로그인</TableHead>
            <TableHead className="w-[100px]">상태</TableHead>
            <TableHead>메모</TableHead>
            <TableHead className="w-[120px] text-right">액션</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {users.map((u) => (
            <TableRow key={u.id} className="[&_td]:py-3">
              <TableCell>
                <div className="flex items-center gap-3">
                  {u.imageUrl ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={u.imageUrl}
                      alt=""
                      className="h-8 w-8 shrink-0 rounded-full object-cover"
                    />
                  ) : (
                    <div className="h-8 w-8 shrink-0 rounded-full bg-muted" />
                  )}
                  <div className="min-w-0">
                    <div className="truncate font-medium">{u.name || "(이름 미설정)"}</div>
                    <div className="truncate text-xs text-muted-foreground">{u.email}</div>
                  </div>
                </div>
              </TableCell>
              <TableCell className="tabular-nums">{fmtDate(u.createdAt)}</TableCell>
              <TableCell className="tabular-nums">{fmtDateTime(u.lastSignInAt)}</TableCell>
              <TableCell>
                {u.banned ? (
                  <span className="inline-flex items-center rounded-full bg-destructive/10 px-2.5 py-1 text-xs font-semibold text-destructive ring-1 ring-destructive/20">
                    차단됨
                  </span>
                ) : (
                  <span className="inline-flex items-center rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700 ring-1 ring-emerald-200">
                    정상
                  </span>
                )}
              </TableCell>
              <TableCell>
                <MemoInput userId={u.id} initialMemo={u.memo} />
              </TableCell>
              <TableCell className="text-right">
                <BanButton userId={u.id} banned={u.banned} userLabel={u.email} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
