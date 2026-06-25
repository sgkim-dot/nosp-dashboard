"use client";

import { useState, useTransition } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { updateMemoAction } from "@/app/users/actions";

export function MemoInput({
  userId,
  initialMemo,
}: {
  userId: string;
  initialMemo: string;
}) {
  const [value, setValue] = useState(initialMemo);
  const [savedValue, setSavedValue] = useState(initialMemo);
  const [isPending, startTransition] = useTransition();
  const dirty = value !== savedValue;

  const handleSave = () => {
    startTransition(async () => {
      await updateMemoAction(userId, value);
      setSavedValue(value);
    });
  };

  return (
    <div className="flex items-center gap-2">
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="메모 (예: 광고팀 김OO 대리)"
        disabled={isPending}
        className="flex-1 rounded-md border border-input bg-background px-2.5 py-1.5 text-sm placeholder:text-muted-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40 disabled:opacity-60"
      />
      <Button
        variant="outline"
        size="sm"
        disabled={!dirty || isPending}
        onClick={handleSave}
      >
        {isPending ? <Loader2 className="animate-spin" /> : null}
        저장
      </Button>
    </div>
  );
}
