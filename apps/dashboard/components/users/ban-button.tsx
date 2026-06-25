"use client";

import { useTransition } from "react";
import { Loader2, Ban, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { banUserAction, unbanUserAction } from "@/app/users/actions";

export function BanButton({
  userId,
  banned,
  userLabel,
}: {
  userId: string;
  banned: boolean;
  userLabel: string;
}) {
  const [isPending, startTransition] = useTransition();

  const handleClick = () => {
    const msg = banned
      ? `${userLabel} 의 차단을 해제할까요?`
      : `${userLabel} 의 접속을 차단할까요?\n로그인이 막히며, 언제든 다시 해제할 수 있습니다.`;
    if (!window.confirm(msg)) return;
    startTransition(async () => {
      if (banned) {
        await unbanUserAction(userId);
      } else {
        await banUserAction(userId);
      }
    });
  };

  return (
    <Button
      variant={banned ? "outline" : "destructive"}
      size="sm"
      onClick={handleClick}
      disabled={isPending}
    >
      {isPending ? (
        <Loader2 className="animate-spin" />
      ) : banned ? (
        <RotateCcw />
      ) : (
        <Ban />
      )}
      {banned ? "차단 해제" : "차단"}
    </Button>
  );
}
