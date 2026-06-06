"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

export default function RefreshButton() {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [justDone, setJustDone] = useState(false);

  const handleRefresh = () => {
    startTransition(() => {
      router.refresh();
    });
    // 2 saniye sonra "✓" göster
    setJustDone(false);
    const t = setTimeout(() => {
      setJustDone(true);
      setTimeout(() => setJustDone(false), 1500);
    }, 600);
    return () => clearTimeout(t);
  };

  return (
    <button
      onClick={handleRefresh}
      disabled={isPending}
      title="Veriyi yenile"
      className={`
        flex items-center justify-center w-7 h-7 rounded border text-xs font-mono
        transition-all duration-200 select-none
        ${isPending
          ? "border-eyay-border text-eyay-faint bg-eyay-raised cursor-wait"
          : justDone
            ? "border-emerald-800 text-emerald-400 bg-emerald-950/30"
            : "border-eyay-border text-eyay-dim bg-eyay-raised hover:border-blue-700 hover:text-blue-400 hover:bg-blue-950/30 cursor-pointer"
        }
      `}
    >
      <span
        className={`transition-transform duration-300 ${isPending ? "animate-spin" : ""}`}
        style={{ display: "inline-block" }}
      >
        {justDone ? "✓" : "↺"}
      </span>
    </button>
  );
}
