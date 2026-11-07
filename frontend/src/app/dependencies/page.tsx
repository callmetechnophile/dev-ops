"use client";

import React, { useEffect, useState, useMemo } from "react";
import ReactFlow, { 
  Background, 
  Controls, 
  MiniMap, 
  Node, 
  Edge,
  MarkerType
} from "reactflow";
import "reactflow/dist/style.css";
import { GitFork, Layers, ShieldCheck } from "lucide-react";
import { fetchServices, fetchServiceDependencies } from "@/lib/api";
import { StatusBadge } from "@/components/status-badge";

export default function DependencyExplorerPage() {
  const [services, setServices] = useState<any[]>([]);
  const [dependencies, setDependencies] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetchServices();
        const svcs = res.items || [];
        setServices(svcs);

        const depPromises = svcs.map((s: any) =>
          fetchServiceDependencies(s.id).catch(() => [])
        );
        const depResults = await Promise.all(depPromises);
        setDependencies(depResults.flat());
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  // Compute React Flow nodes & edges
  const { nodes, edges } = useMemo(() => {
    const nodeItems: Node[] = services.map((s, idx) => ({
      id: s.id,
      position: { x: (idx % 3) * 260 + 50, y: Math.floor(idx / 3) * 160 + 50 },
      data: {
        label: (
          <div className="p-3 rounded-lg bg-card border border-border text-xs font-mono text-foreground space-y-1 shadow-md min-w-[180px]">
            <div className="font-bold flex items-center justify-between">
              <span>{s.name}</span>
              <span className="text-[9px] uppercase px-1 py-0.5 rounded bg-muted text-muted-foreground">
                {s.tier}
              </span>
            </div>
            <div className="text-[10px] text-muted-foreground flex items-center justify-between">
              <span>Health:</span>
              <StatusBadge status={s.health_status} />
            </div>
          </div>
        ),
      },
      style: { background: "transparent", border: "none" },
    }));

    const edgeItems: Edge[] = dependencies.map((d) => ({
      id: d.id,
      source: d.source_service_id,
      target: d.target_service_id,
      animated: true,
      label: d.dependency_type,
      labelStyle: { fill: "#94a3b8", fontSize: 10, fontFamily: "monospace" },
      style: { stroke: "#38bdf8", strokeWidth: 2 },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: "#38bdf8",
      },
    }));

    return { nodes: nodeItems, edges: edgeItems };
  }, [services, dependencies]);

  return (
    <div className="space-y-4 max-w-7xl mx-auto h-[calc(100vh-100px)] flex flex-col">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
          <GitFork className="h-5 w-5 text-accent" />
          Service Dependency & Blast Radius Explorer
        </h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          Relational topology mapping upstream caller dependencies and downstream blast radius consequences.
        </p>
      </div>

      <div className="flex-1 rounded-lg border border-border bg-card/30 overflow-hidden relative">
        {services.length === 0 ? (
          <div className="h-full flex items-center justify-center p-8 text-center text-xs text-muted-foreground font-mono">
            No registered services in topology map.
          </div>
        ) : (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            fitView
            className="bg-[#090d16]"
          >
            <Background color="#1e293b" gap={16} />
            <Controls className="bg-card border-border fill-foreground" />
            <MiniMap 
              nodeColor="#38bdf8" 
              maskColor="rgba(9, 13, 22, 0.8)" 
              className="bg-card border border-border" 
            />
          </ReactFlow>
        )}
      </div>
    </div>
  );
}
