"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  BrainCircuit,
  Search,
  BookOpen,
  CheckCircle2,
  ShieldAlert,
  Sparkles,
  ExternalLink,
  Layers,
  Clock,
  Filter,
} from "lucide-react";
import { searchMemory, fetchOperationalLessons } from "@/lib/api";
import { formatDate } from "@/lib/utils";

export default function OperationalMemoryPage() {
  const [query, setQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("ALL");
  const [envFilter, setEnvFilter] = useState("ALL");
  const [verifiedOnly, setVerifiedOnly] = useState(true);
  const [searchResults, setSearchResults] = useState<any[] | null>(null);
  const [initialLessons, setInitialLessons] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    async function loadLessons() {
      try {
        const res = await fetchOperationalLessons();
        setInitialLessons(res?.items || []);
      } catch (err) {
        console.error("Failed to load initial lessons:", err);
      }
    }
    loadLessons();
  }, []);

  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!query.trim()) {
      setSearchResults(null);
      return;
    }
    setLoading(true);
    try {
      const cat = categoryFilter !== "ALL" ? categoryFilter : undefined;
      const env = envFilter !== "ALL" ? envFilter : undefined;
      const data = await searchMemory(query.trim(), cat, env);
      setSearchResults(data?.results || []);
    } catch (err) {
      console.error("Search failed:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Title */}
      <div>
        <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
          <BrainCircuit className="h-5 w-5 text-cyan-400" />
          Persistent Operational Memory
        </h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          Episodic incident history, relational failure chains, and semantic retrieval of human-verified engineering lessons.
        </p>
      </div>

      {/* Memory Layer Highlights */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-4 rounded border border-border bg-card/60 space-y-1">
          <div className="text-xs font-mono text-cyan-400 font-semibold flex items-center gap-1.5">
            <BookOpen className="h-4 w-4" />
            EPISODIC MEMORY
          </div>
          <div className="text-xs text-muted-foreground">
            Immutable log of historical incidents, timelines, and recovery transitions stored in PostgreSQL.
          </div>
        </div>

        <div className="p-4 rounded border border-border bg-card/60 space-y-1">
          <div className="text-xs font-mono text-emerald-400 font-semibold flex items-center gap-1.5">
            <CheckCircle2 className="h-4 w-4" />
            VERIFIED LESSONS ({initialLessons.length})
          </div>
          <div className="text-xs text-muted-foreground">
            Human-confirmed post-mortem lessons preventing identical failure modes in future deployments.
          </div>
        </div>

        <div className="p-4 rounded border border-border bg-card/60 space-y-1">
          <div className="text-xs font-mono text-purple-400 font-semibold flex items-center gap-1.5">
            <Sparkles className="h-4 w-4" />
            SEMANTIC MEMORY
          </div>
          <div className="text-xs text-muted-foreground">
            Searchable pgvector embeddings with deterministic lexical fallback for instant retrieval.
          </div>
        </div>
      </div>

      {/* Search & Filter Bar */}
      <div className="p-4 rounded border border-border bg-card/60 space-y-3">
        <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search operational memory (e.g., 'CrashLoopBackOff', 'connection pool', 'OOMKilled')..."
              className="w-full pl-9 pr-4 py-2 rounded bg-secondary/40 border border-border text-xs text-foreground placeholder:text-muted-foreground font-mono focus:outline-none focus:border-cyan-400"
            />
          </div>

          <div className="flex items-center gap-2">
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="bg-secondary/60 border border-border text-xs font-mono rounded px-3 py-2 text-foreground focus:outline-none"
            >
              <option value="ALL">All Categories</option>
              <option value="BUILD_FAILURE">BUILD_FAILURE</option>
              <option value="DEPLOYMENT_FAILURE">DEPLOYMENT_FAILURE</option>
              <option value="CONFIGURATION_FAILURE">CONFIGURATION_FAILURE</option>
              <option value="INFRASTRUCTURE_FAILURE">INFRASTRUCTURE_FAILURE</option>
            </select>

            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 rounded bg-cyan-500 hover:bg-cyan-600 text-black font-mono text-xs font-bold transition-colors disabled:opacity-50"
            >
              {loading ? "Searching..." : "Retrieve Memory"}
            </button>
          </div>
        </form>

        <div className="flex items-center justify-between text-xs font-mono text-muted-foreground pt-1">
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-1.5 cursor-pointer">
              <input
                type="checkbox"
                checked={verifiedOnly}
                onChange={(e) => setVerifiedOnly(e.target.checked)}
                className="rounded border-border"
              />
              <span>Human-Verified Knowledge Only</span>
            </label>
          </div>
          <span>Tenant Isolated Search</span>
        </div>
      </div>

      {/* Search Results or Initial Lessons */}
      <div className="space-y-4">
        <div className="flex items-center justify-between text-xs font-mono text-muted-foreground font-semibold px-1">
          <span>
            {searchResults !== null
              ? `Search Results (${searchResults.length} matches)`
              : `Verified Operational Lessons (${initialLessons.length})`}
          </span>
          {searchResults !== null && (
            <button onClick={() => setSearchResults(null)} className="text-cyan-400 hover:underline">
              Clear Search
            </button>
          )}
        </div>

        {/* Display Search Results */}
        {searchResults !== null ? (
          searchResults.length === 0 ? (
            <div className="p-12 text-center text-xs font-mono text-muted-foreground border border-dashed border-border rounded">
              No matching operational memory records found for query "{query}".
            </div>
          ) : (
            <div className="space-y-3">
              {searchResults.map((item) => (
                <div key={item.id} className="p-4 rounded border border-border bg-card/60 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold uppercase ${
                          item.verification_status === "VERIFIED"
                            ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/30"
                            : "bg-secondary text-muted-foreground border border-border"
                        }`}
                      >
                        {item.verification_status} {item.record_type.replace("_", " ")}
                      </span>
                      {item.relevance_score && (
                        <span className="text-[10px] font-mono text-muted-foreground">
                          Relevance: {Math.round(item.relevance_score * 100)}%
                        </span>
                      )}
                      {item.incident_key && (
                        <span className="text-[10px] font-mono text-rose-400 font-bold">
                          {item.incident_key}
                        </span>
                      )}
                    </div>
                    {item.incident_id && (
                      <Link
                        href={`/incidents/${item.incident_id}`}
                        className="text-xs font-mono text-cyan-400 hover:underline inline-flex items-center gap-1"
                      >
                        <span>View Incident</span>
                        <ExternalLink className="h-3 w-3" />
                      </Link>
                    )}
                  </div>

                  <h3 className="text-sm font-bold font-mono text-foreground">{item.title}</h3>
                  <p className="text-xs text-muted-foreground whitespace-pre-line">{item.summary}</p>
                </div>
              ))}
            </div>
          )
        ) : initialLessons.length === 0 ? (
          <div className="p-16 text-center space-y-2 border border-dashed border-border rounded">
            <BookOpen className="h-8 w-8 text-muted-foreground mx-auto opacity-40" />
            <div className="text-xs font-mono text-foreground font-semibold">No Verified Lessons Yet</div>
            <div className="text-[11px] text-muted-foreground max-w-sm mx-auto">
              When engineers confirm root-cause hypotheses on incidents, verified engineering lessons and prevention strategies are permanently indexed here.
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            {initialLessons.map((l) => (
              <div key={l.id} className="p-4 rounded border border-cyan-500/20 bg-cyan-950/10 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded font-bold uppercase bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 flex items-center gap-1">
                      <CheckCircle2 className="h-3 w-3" />
                      VERIFIED LESSON
                    </span>
                    <span className="text-[10px] font-mono text-muted-foreground">
                      {formatDate(l.created_at)}
                    </span>
                  </div>
                  <Link
                    href={`/incidents/${l.incident_id}`}
                    className="text-xs font-mono text-cyan-400 hover:underline inline-flex items-center gap-1"
                  >
                    <span>Linked Incident</span>
                    <ExternalLink className="h-3 w-3" />
                  </Link>
                </div>

                <h3 className="text-sm font-bold font-mono text-foreground">{l.title}</h3>
                <p className="text-xs text-muted-foreground whitespace-pre-line">{l.lesson}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
