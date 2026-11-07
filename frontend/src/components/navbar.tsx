import React from "react";
import Link from "next/link";
import { ShieldAlert, Activity, GitBranch, Cpu, Terminal } from "lucide-react";

export function Navbar() {
  return (
    <header className="h-14 border-b border-border bg-card/60 backdrop-blur-md px-6 flex items-center justify-between sticky top-0 z-50">
      <div className="flex items-center gap-3">
        <div className="p-1.5 rounded-md bg-accent/10 border border-accent/30 text-accent">
          <ShieldAlert className="h-5 w-5" />
        </div>
        <div className="flex items-center gap-2">
          <span className="font-semibold text-sm tracking-wide text-foreground">
            PREDICTIVE DEVOPS INTELLIGENCE
          </span>
          <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-muted text-muted-foreground border border-border">
            v1.0.0
          </span>
        </div>
      </div>

      <div className="flex items-center gap-4 text-xs font-mono text-muted-foreground">
        <div className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-foreground">AGENT: ONLINE</span>
        </div>
        <span className="text-border">|</span>
        <div className="flex items-center gap-1.5">
          <Cpu className="h-3.5 w-3.5 text-accent" />
          <span>AUTONOMY: HUMAN GATED</span>
        </div>
        <span className="text-border">|</span>
        <div className="flex items-center gap-1.5">
          <Terminal className="h-3.5 w-3.5 text-muted-foreground" />
          <span>TENANT: ACME-CORP</span>
        </div>
      </div>
    </header>
  );
}
