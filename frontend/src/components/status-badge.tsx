import React from "react";
import { cn } from "@/lib/utils";

interface StatusBadgeProps {
  status: string;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const s = status.toUpperCase();
  let color = "bg-muted text-muted-foreground border-border";

  if (["SUCCEEDED", "HEALTHY", "APPROVED", "RESOLVED"].includes(s)) {
    color = "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
  } else if (["FAILED", "CRITICAL", "REJECTED", "UNHEALTHY", "HIGH"].includes(s)) {
    color = "bg-rose-500/10 text-rose-400 border-rose-500/30";
  } else if (["WAITING_FOR_APPROVAL", "DEGRADED", "MEDIUM", "WARNING"].includes(s)) {
    color = "bg-amber-500/10 text-amber-400 border-amber-500/30";
  } else if (["PENDING", "IN_PROGRESS", "RUNNING", "LOW"].includes(s)) {
    color = "bg-sky-500/10 text-sky-400 border-sky-500/30";
  }

  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-medium border uppercase tracking-wider",
        color,
        className
      )}
    >
      {status}
    </span>
  );
}
