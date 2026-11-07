"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { 
  LayoutDashboard, 
  Rocket, 
  AlertTriangle, 
  GitFork, 
  BrainCircuit, 
  CheckCheck, 
  Sliders, 
  Activity 
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { label: "Overview", href: "/", icon: LayoutDashboard },
  { label: "Deployments", href: "/deployments", icon: Rocket },
  { label: "Risk Assessment", href: "/risk", icon: AlertTriangle },
  { label: "Incident Memory", href: "/incidents", icon: Activity },
  { label: "Dependency Map", href: "/dependencies", icon: GitFork },
  { label: "Operational Memory", href: "/memory", icon: BrainCircuit },
  { label: "Approval Center", href: "/approvals", icon: CheckCheck },
  { label: "Integrations", href: "/settings", icon: Sliders },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-56 border-r border-border bg-card/30 flex flex-col justify-between p-3 select-none">
      <div className="space-y-1">
        <div className="px-3 py-2 text-[10px] font-mono uppercase tracking-wider text-muted-foreground font-semibold">
          Platform Navigation
        </div>
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href || (item.href !== "/" && pathname?.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-2.5 px-3 py-2 rounded text-xs font-medium transition-colors",
                isActive
                  ? "bg-accent/10 text-accent border border-accent/20"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </div>

      <div className="p-3 border border-border/60 rounded bg-background/50 space-y-1.5 text-[11px] font-mono">
        <div className="text-muted-foreground uppercase text-[9px] tracking-wider font-semibold">
          Execution Policy
        </div>
        <p className="text-muted-foreground leading-relaxed">
          Operational interventions require signed human approval. Autonomous prod mutations disabled.
        </p>
      </div>
    </aside>
  );
}
