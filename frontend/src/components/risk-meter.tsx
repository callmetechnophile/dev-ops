import React from "react";
import { cn } from "@/lib/utils";

interface RiskMeterProps {
  score: number; // 0.00 to 1.00
  label?: string;
  showPercent?: boolean;
}

export function RiskMeter({ score, label, showPercent = true }: RiskMeterProps) {
  const percentage = Math.round(score * 100);
  let barColor = "bg-emerald-500";
  let textColor = "text-emerald-400";

  if (score >= 0.75) {
    barColor = "bg-rose-500";
    textColor = "text-rose-400";
  } else if (score >= 0.45) {
    barColor = "bg-amber-500";
    textColor = "text-amber-400";
  }

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs font-mono">
        <span className="text-muted-foreground">{label || "Risk Score"}</span>
        <span className={cn("font-bold", textColor)}>
          {showPercent ? `${percentage}%` : score.toFixed(2)}
        </span>
      </div>
      <div className="h-1.5 w-full bg-border rounded-full overflow-hidden">
        <div
          className={cn("h-full transition-all duration-500", barColor)}
          style={{ width: `${Math.min(100, Math.max(0, percentage))}%` }}
        />
      </div>
    </div>
  );
}
