"use client";

import React, { useState } from "react";
import { BrainCircuit, Search, BookOpen, AlertOctagon, Sparkles } from "lucide-react";
import { searchMemory } from "@/lib/api";
import { formatDate } from "@/lib/utils";

export default function OperationalMemoryPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    try {
      const data = await searchMemory(query.trim());
      setResults(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
          <BrainCircuit className="h-5 w-5 text-accent" />
          Persistent Operational Memory
        </h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          Semantic retrieval of verified post-mortem engineering lessons, past failure patterns, and architectural mitigations.
        </p>
      </div>

      {/* Query Bar */}
      <form onSubmit={handleSearch} className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search operational memory (e.g. 'connection pool exhaustion', 'CrashLoopBackOff', 'OOMKilled')..."
            className="w-full pl-9 pr-4 py-2 rounded-lg bg-card border border-border text-xs text-foreground placeholder:text-muted-foreground font-mono focus:outline-none focus:border-accent"
          />
        </div>
        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="px-4 py-2 rounded-lg bg-accent text-slate-950 font-mono text-xs font-semibold hover:bg-accent/90 transition-colors disabled:opacity-50"
        >
          {loading ? "Searching..." : "Retrieve Memory"}
        </button>
      </form>

      {/* Results */}
      {results ? (
        <div className="space-y-6 font-mono">
          <div className="text-xs text-muted-foreground">
            Found <span className="text-foreground font-bold">{results.total_matches}</span> matching records in operational memory for query: &quot;{results.query}&quot;
          </div>

          {/* Verified Engineering Lessons */}
          <div className="space-y-3">
            <h2 className="text-xs uppercase font-semibold text-foreground flex items-center gap-1.5">
              <BookOpen className="h-4 w-4 text-emerald-400" />
              Verified Engineering Lessons ({results.verified_lessons?.length || 0})
            </h2>

            {results.verified_lessons?.length === 0 ? (
              <div className="p-4 rounded border border-border bg-card/40 text-xs text-muted-foreground">
                No verified lessons matched this query.
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {results.verified_lessons.map((lesson: any) => (
                  <div key={lesson.id} className="p-4 rounded-lg bg-card border border-border space-y-2 text-xs">
                    <div className="font-bold text-emerald-300">
                      {lesson.root_cause_summary}
                    </div>
                    <div className="text-muted-foreground">
                      <span className="text-foreground font-semibold">Lesson: </span>
                      {lesson.verified_engineering_lesson}
                    </div>
                    <div className="text-muted-foreground">
                      <span className="text-foreground font-semibold">Mitigation: </span>
                      {lesson.prevention_strategy}
                    </div>
                    <div className="text-[10px] text-muted-foreground pt-1 border-t border-border">
                      Confirmed: {formatDate(lesson.confirmed_at)}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Historical Failure Signatures */}
          <div className="space-y-3">
            <h2 className="text-xs uppercase font-semibold text-foreground flex items-center gap-1.5">
              <AlertOctagon className="h-4 w-4 text-rose-400" />
              Historical Failure Signatures ({results.historical_failures?.length || 0})
            </h2>

            {results.historical_failures?.length === 0 ? (
              <div className="p-4 rounded border border-border bg-card/40 text-xs text-muted-foreground">
                No matching failure signatures found.
              </div>
            ) : (
              <div className="space-y-2">
                {results.historical_failures.map((f: any) => (
                  <div key={f.id} className="p-3 rounded bg-card border border-border flex items-center justify-between text-xs">
                    <div>
                      <span className="font-bold text-rose-400">{f.failure_type}</span>
                      <div className="text-muted-foreground text-[11px] mt-0.5">{f.error_message}</div>
                    </div>
                    <span className="text-muted-foreground text-[10px]">
                      Exit Code: {f.exit_code ?? "—"}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="p-12 text-center border border-dashed border-border rounded-lg bg-card/20 space-y-2 font-mono">
          <Sparkles className="h-6 w-6 text-accent mx-auto" />
          <div className="text-xs text-foreground font-semibold">Semantic Knowledge Base Ready</div>
          <p className="text-[11px] text-muted-foreground max-w-sm mx-auto">
            Search across past post-mortems and failure lessons to understand risks before initiating new production rollouts.
          </p>
        </div>
      )}
    </div>
  );
}
