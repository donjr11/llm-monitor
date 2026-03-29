"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Activity,
  RefreshCw,
  Brain,
  Zap,
  DollarSign,
  Sparkles,
  Database,
  Award,
  ChevronUp,
  ChevronDown,
  Shield,
  Search,
  BarChart3,
  BookOpen,
  Code,
  Bot,
  Clock,
  AlertCircle,
  TrendingUp,
} from "lucide-react";

// ─── Types ───────────────────────────────────────────────────────────────────

interface Model {
  name: string;
  provider: string | null;
  source: string;
  license_type: string | null;
  intelligence_score: number | null;
  price_input: number | null;
  price_output: number | null;
  speed_tps: number | null;
  ttft_ms: number | null;
  context_window: number | null;
  norm_intelligence: number | null;
  norm_price: number | null;
  norm_speed: number | null;
  norm_ttft: number | null;
  norm_context: number | null;
  is_new: boolean;
  collected_at: string | null;
}

interface ResultMetrics {
  intelligence: number | null;
  price_input: number | null;
  price_output: number | null;
  speed_tps: number | null;
  ttft_ms: number | null;
  context_window: number | null;
  license: string | null;
}

interface RecommendedModel {
  rank: number;
  name: string;
  provider: string | null;
  score: number;
  justification: string | null;
  metrics: ResultMetrics;
}

interface Recommendation {
  profile: string;
  method: string;
  results: RecommendedModel[];
}

// ─── Constants ────────────────────────────────────────────────────────────────

const API = "http://localhost:8000";

const PROFILES = [
  { key: "coding",            label: "Coding / Dev",         icon: Code },
  { key: "reasoning",         label: "Reasoning / Analysis", icon: Brain },
  { key: "rag_long_context",  label: "Long Context RAG",     icon: BookOpen },
  { key: "minimum_cost",      label: "Minimum Cost",         icon: DollarSign },
  { key: "enterprise_agents", label: "Enterprise Agents",    icon: Bot },
];

const MEDALS = ["🥇", "🥈", "🥉"];

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmt(v: number | null, d = 1): string {
  return v == null ? "—" : v.toFixed(d);
}

function fmtCtx(v: number | null): string {
  if (v == null) return "—";
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `${Math.round(v / 1_000)}K`;
  return `${v}`;
}

function fmtPrice(v: number | null): string {
  if (v == null) return "—";
  if (v < 0.01) return `$${v.toFixed(4)}`;
  return `$${v.toFixed(2)}`;
}

function srcLabel(s: string): string {
  return { huggingface: "HF", artificial_analysis: "AA", llm_stats: "LS" }[s] ?? s;
}

function srcColor(s: string): string {
  return (
    { huggingface: "bg-orange-500/15 text-orange-400 border-orange-500/25",
      artificial_analysis: "bg-violet-500/15 text-violet-400 border-violet-500/25",
      llm_stats: "bg-sky-500/15 text-sky-400 border-sky-500/25",
    }[s] ?? "bg-slate-500/15 text-slate-400 border-slate-500/25"
  );
}

function licenseIsOpen(t: string | null): boolean {
  if (!t) return false;
  return ["apache", "mit", "cc-by", "llama", "gemma", "qwen"].some(k =>
    t.toLowerCase().includes(k)
  );
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function ScoreBar({
  value,
  className = "",
}: {
  value: number | null;
  className?: string;
}) {
  const pct = value != null ? Math.min(100, Math.round(value * 100)) : 0;
  const grad =
    pct >= 75
      ? "from-cyan-400 to-teal-400"
      : pct >= 50
      ? "from-blue-400 to-cyan-400"
      : "from-slate-500 to-slate-400";
  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <div className="flex-1 h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
        <div
          className={`h-full rounded-full bg-gradient-to-r ${grad} transition-all duration-700 ease-out`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-[11px] tabular-nums text-slate-500 w-8 text-right">{pct}%</span>
    </div>
  );
}

function LicenseBadge({ type }: { type: string | null }) {
  if (!type) return null;
  const open = licenseIsOpen(type);
  return (
    <span
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium border uppercase tracking-wide
      ${open
        ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
        : "bg-amber-500/10 text-amber-400 border-amber-500/20"
      }`}
    >
      <Shield className="w-2.5 h-2.5" />
      {type.length > 14 ? type.slice(0, 12) + "…" : type}
    </span>
  );
}

function SourceBadge({ source }: { source: string }) {
  return (
    <span
      className={`inline-flex px-1.5 py-0.5 rounded text-[10px] font-medium border uppercase tracking-wide ${srcColor(source)}`}
    >
      {srcLabel(source)}
    </span>
  );
}

function Skeleton({ className }: { className?: string }) {
  return (
    <div className={`rounded-lg bg-white/[0.05] animate-pulse ${className}`} />
  );
}

// ─── Dashboard ────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const [models, setModels] = useState<Model[]>([]);
  const [newModels, setNewModels] = useState<Model[]>([]);
  const [rec, setRec] = useState<Recommendation | null>(null);
  const [profile, setProfile] = useState("coding");
  const [commercial, setCommercial] = useState(false);
  const [method, setMethod] = useState<"ahp_topsis" | "topsis">("ahp_topsis");
  const [loadingModels, setLoadingModels] = useState(true);
  const [loadingRec, setLoadingRec] = useState(true);
  const [apiError, setApiError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [srcFilter, setSrcFilter] = useState("all");
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [sortField, setSortField] = useState("intelligence_score");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  // ── Fetchers ──────────────────────────────────────────────────────────────

  const fetchModels = useCallback(async () => {
    setLoadingModels(true);
    try {
      const [mRes, nRes] = await Promise.all([
        fetch(`${API}/models`),
        fetch(`${API}/models/new`),
      ]);
      if (!mRes.ok) throw new Error("API unreachable");
      const mData = await mRes.json();
      const nData = await nRes.json();
      setModels(mData.models ?? []);
      setNewModels(nData.models ?? []);
      setLastUpdated(new Date());
      setApiError(null);
    } catch {
      setApiError("Cannot reach the API — make sure the backend is running on port 8000.");
    } finally {
      setLoadingModels(false);
    }
  }, []);

  const fetchRec = useCallback(async () => {
    setLoadingRec(true);
    try {
      const res = await fetch(
        `${API}/recommend?profile=${profile}&commercial=${commercial}&top_n=3&method=${method}`
      );
      if (res.ok) setRec(await res.json());
    } catch {
      // silently fail — models table still works
    } finally {
      setLoadingRec(false);
    }
  }, [profile, commercial, method]);

  useEffect(() => {
    fetchModels();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    fetchRec();
  }, [fetchRec]);

  // ── Derived data ──────────────────────────────────────────────────────────

  const withIQ = models.filter((m) => m.intelligence_score != null);
  const avgIQ =
    withIQ.length > 0
      ? withIQ.reduce((s, m) => s + m.intelligence_score!, 0) / withIQ.length
      : null;

  const filtered = models
    .filter((m) => {
      if (srcFilter !== "all" && m.source !== srcFilter) return false;
      if (search && !m.name.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    })
    .sort((a, b) => {
      const av = ((a as unknown) as Record<string, unknown>)[sortField] as number ?? -1;
      const bv = ((b as unknown) as Record<string, unknown>)[sortField] as number ?? -1;
      return sortDir === "desc" ? bv - av : av - bv;
    });

  function toggleSort(field: string) {
    if (sortField === field) setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    else {
      setSortField(field);
      setSortDir("desc");
    }
  }

  const activeProfile = PROFILES.find((p) => p.key === profile);

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-[#070d1a] text-slate-200">

      {/* ──────────────── HEADER ──────────────── */}
      <header className="sticky top-0 z-50 border-b border-white/[0.06] bg-[#070d1a]/90 backdrop-blur-xl">
        <div className="max-w-screen-2xl mx-auto px-6 h-14 flex items-center justify-between gap-4">
          {/* Brand */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-md bg-gradient-to-br from-cyan-400 to-blue-600 flex items-center justify-center flex-shrink-0">
                <BarChart3 className="w-3.5 h-3.5 text-white" />
              </div>
              <div className="flex items-baseline gap-1.5">
                <span className="text-sm font-bold tracking-widest text-white uppercase">
                  EPINEON
                </span>
                <span className="text-sm font-bold text-cyan-400 tracking-widest uppercase">AI</span>
              </div>
            </div>
            <div className="hidden sm:block h-4 w-px bg-white/10" />
            <span className="hidden sm:block text-sm text-slate-500 font-medium">
              LLM Monitor
            </span>
          </div>

          {/* Right controls */}
          <div className="flex items-center gap-3">
            {lastUpdated && (
              <span className="hidden md:block text-xs text-slate-600">
                {lastUpdated.toLocaleTimeString()}
              </span>
            )}
            <div className="flex items-center gap-1.5 text-xs text-emerald-400">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
              </span>
              <span className="hidden sm:block">Live</span>
            </div>
            <button
              onClick={() => { fetchModels(); fetchRec(); }}
              disabled={loadingModels}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-white/[0.05] hover:bg-white/[0.08] border border-white/[0.08] text-slate-300 transition-all disabled:opacity-50 cursor-pointer"
            >
              <RefreshCw className={`w-3 h-3 ${loadingModels ? "animate-spin" : ""}`} />
              <span className="hidden sm:block">Refresh</span>
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-screen-2xl mx-auto px-6 py-8 space-y-8">

        {/* ──────────────── API ERROR ──────────────── */}
        {apiError && (
          <div className="flex items-center gap-3 px-4 py-3 rounded-xl border border-red-500/20 bg-red-500/5 text-sm text-red-400">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            {apiError}
          </div>
        )}

        {/* ──────────────── KPI ROW ──────────────── */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Total Models */}
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-5">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-[11px] uppercase tracking-widest text-slate-500 font-medium">Models</p>
                {loadingModels
                  ? <Skeleton className="h-8 w-12 mt-2" />
                  : <div className="text-3xl font-bold text-white mt-1 tabular-nums">{models.length || "—"}</div>}
                <p className="text-xs text-slate-600 mt-1">Total tracked</p>
              </div>
              <div className="w-9 h-9 rounded-lg bg-white/[0.04] flex items-center justify-center">
                <Database className="w-4 h-4 text-slate-500" />
              </div>
            </div>
          </div>

          {/* New Models */}
          <div className={`rounded-xl border p-5 ${newModels.length > 0 ? "border-cyan-500/25 bg-cyan-500/[0.04]" : "border-white/[0.06] bg-white/[0.02]"}`}>
            <div className="flex items-start justify-between">
              <div>
                <p className="text-[11px] uppercase tracking-widest text-slate-500 font-medium">New</p>
                {loadingModels
                  ? <Skeleton className="h-8 w-8 mt-2" />
                  : <div className={`text-3xl font-bold mt-1 tabular-nums ${newModels.length > 0 ? "text-cyan-400" : "text-white"}`}>{newModels.length}</div>}
                <p className="text-xs text-slate-600 mt-1">Latest run</p>
              </div>
              <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${newModels.length > 0 ? "bg-cyan-500/15" : "bg-white/[0.04]"}`}>
                <Sparkles className={`w-4 h-4 ${newModels.length > 0 ? "text-cyan-400" : "text-slate-500"}`} />
              </div>
            </div>
          </div>

          {/* Profiles */}
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-5">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-[11px] uppercase tracking-widest text-slate-500 font-medium">Profiles</p>
                <div className="text-3xl font-bold text-white mt-1 tabular-nums">{PROFILES.length}</div>
                <p className="text-xs text-slate-600 mt-1">Enterprise</p>
              </div>
              <div className="w-9 h-9 rounded-lg bg-white/[0.04] flex items-center justify-center">
                <Award className="w-4 h-4 text-slate-500" />
              </div>
            </div>
          </div>

          {/* Avg IQ */}
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-5">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-[11px] uppercase tracking-widest text-slate-500 font-medium">Avg IQ</p>
                {loadingModels
                  ? <Skeleton className="h-8 w-16 mt-2" />
                  : <div className="text-3xl font-bold text-white mt-1 tabular-nums">{fmt(avgIQ)}</div>}
                <p className="text-xs text-slate-600 mt-1">Intelligence score</p>
              </div>
              <div className="w-9 h-9 rounded-lg bg-white/[0.04] flex items-center justify-center">
                <TrendingUp className="w-4 h-4 text-slate-500" />
              </div>
            </div>
          </div>
        </div>

        {/* ──────────────── MAIN GRID ──────────────── */}
        <div className="grid grid-cols-1 xl:grid-cols-5 gap-6">

          {/* ── LEFT: Profile + Recommendations ── */}
          <div className="xl:col-span-2 space-y-5">
            <h2 className="text-sm font-semibold text-white flex items-center gap-2">
              <Award className="w-4 h-4 text-cyan-400" />
              Top Recommendations
              <span className="text-[10px] font-normal text-slate-600 uppercase tracking-wide">
                {method === "ahp_topsis" ? "AHP+TOPSIS" : "TOPSIS"}
              </span>
            </h2>

            {/* Profile selector */}
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] overflow-hidden">
              <div className="px-4 py-3 border-b border-white/[0.06]">
                <p className="text-[11px] uppercase tracking-widest text-slate-500 font-medium">
                  Enterprise Profile
                </p>
              </div>
              <div className="p-2 space-y-0.5">
                {PROFILES.map((p) => {
                  const Icon = p.icon;
                  const active = profile === p.key;
                  return (
                    <button
                      key={p.key}
                      onClick={() => setProfile(p.key)}
                      className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm text-left transition-all cursor-pointer
                        ${active
                          ? "bg-cyan-500/15 text-cyan-300 border border-cyan-500/25"
                          : "text-slate-400 hover:bg-white/[0.04] hover:text-slate-200 border border-transparent"
                        }`}
                    >
                      <Icon className="w-3.5 h-3.5 flex-shrink-0" />
                      <span>{p.label}</span>
                      {active && (
                        <span className="ml-auto text-[10px] font-medium text-cyan-500 uppercase tracking-wide">
                          Active
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>

              {/* Scoring method */}
              <div className="px-4 py-3 border-t border-white/[0.06]">
                <p className="text-[11px] uppercase tracking-widest text-slate-500 font-medium mb-2">Scoring Method</p>
                <div className="flex rounded-lg overflow-hidden border border-white/[0.08]">
                  {([
                    { key: "ahp_topsis", label: "AHP + TOPSIS" },
                    { key: "topsis",     label: "TOPSIS only"  },
                  ] as const).map((m, i) => (
                    <button
                      key={m.key}
                      onClick={() => setMethod(m.key)}
                      className={`flex-1 py-1.5 text-[11px] font-medium transition-all cursor-pointer
                        ${i === 0 ? "" : "border-l border-white/[0.08]"}
                        ${method === m.key
                          ? "bg-cyan-500/20 text-cyan-300"
                          : "text-slate-500 hover:text-slate-300 hover:bg-white/[0.04]"
                        }`}
                    >
                      {m.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Commercial toggle */}
              <div className="px-4 py-3 border-t border-white/[0.06] flex items-center justify-between">
                <div>
                  <p className="text-xs text-slate-300 font-medium">Commercial only</p>
                  <p className="text-[10px] text-slate-600 mt-0.5">Exclude non-commercial licenses</p>
                </div>
                <button
                  onClick={() => setCommercial((c) => !c)}
                  className={`relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer items-center rounded-full transition-colors focus:outline-none ${commercial ? "bg-cyan-500" : "bg-white/10"}`}
                >
                  <span
                    className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-sm transition-transform ${commercial ? "translate-x-4" : "translate-x-0.5"}`}
                  />
                </button>
              </div>
            </div>

            {/* Recommendation cards */}
            <div className="space-y-3">
              {loadingRec
                ? [1, 2, 3].map((i) => <Skeleton key={i} className="h-52 w-full" />)
                : rec?.results?.map((m, i) => {
                  // Normalise raw metrics for score bars (approx ranges)
                  const normIQ    = m.metrics.intelligence != null ? m.metrics.intelligence / 100 : null;
                  const normSpeed = m.metrics.speed_tps    != null ? Math.min(m.metrics.speed_tps / 250, 1) : null;
                  const normPrice = m.metrics.price_input  != null ? Math.max(0, 1 - m.metrics.price_input / 20) : null;
                  const normTTFT  = m.metrics.ttft_ms      != null ? Math.max(0, 1 - m.metrics.ttft_ms / 1500) : null;
                  // Look up source + is_new from models list
                  const modelEntry = models.find(x => x.name === m.name);
                  return (
                    <div
                      key={m.name}
                      className={`rounded-xl border p-4 space-y-3.5 transition-all ${
                        i === 0
                          ? "border-cyan-500/30 bg-gradient-to-br from-cyan-500/[0.07] to-blue-600/[0.04]"
                          : "border-white/[0.06] bg-white/[0.02]"
                      }`}
                    >
                      {/* Model header */}
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-center gap-2.5 min-w-0">
                          <span className="text-xl flex-shrink-0">{MEDALS[i]}</span>
                          <div className="min-w-0">
                            <p className="text-sm font-semibold text-white leading-tight truncate">{m.name}</p>
                            <p className="text-xs text-slate-500 mt-0.5">{m.provider ?? "Unknown"}</p>
                          </div>
                        </div>
                        <div className="flex-shrink-0 text-right">
                          <p className={`text-base font-bold tabular-nums ${i === 0 ? "text-cyan-400" : "text-slate-300"}`}>
                            {m.score.toFixed(3)}
                          </p>
                          <p className="text-[10px] text-slate-600 uppercase tracking-wide">TOPSIS</p>
                        </div>
                      </div>

                      {/* Metrics */}
                      <div className="space-y-2">
                        <div>
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-[11px] text-slate-500 flex items-center gap-1"><Brain className="w-3 h-3" /> Intelligence</span>
                            <span className="text-[11px] tabular-nums text-slate-300">{fmt(m.metrics.intelligence)}</span>
                          </div>
                          <ScoreBar value={normIQ} />
                        </div>
                        <div>
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-[11px] text-slate-500 flex items-center gap-1"><Zap className="w-3 h-3" /> Speed</span>
                            <span className="text-[11px] tabular-nums text-slate-300">
                              {m.metrics.speed_tps != null ? `${fmt(m.metrics.speed_tps, 0)} t/s` : "—"}
                            </span>
                          </div>
                          <ScoreBar value={normSpeed} />
                        </div>
                        <div>
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-[11px] text-slate-500 flex items-center gap-1"><DollarSign className="w-3 h-3" /> Cost (input)</span>
                            <span className="text-[11px] tabular-nums text-slate-300">{fmtPrice(m.metrics.price_input)}/1M</span>
                          </div>
                          <ScoreBar value={normPrice} />
                        </div>
                        <div>
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-[11px] text-slate-500 flex items-center gap-1"><Clock className="w-3 h-3" /> TTFT</span>
                            <span className="text-[11px] tabular-nums text-slate-300">
                              {m.metrics.ttft_ms != null ? `${fmt(m.metrics.ttft_ms, 0)} ms` : "—"}
                            </span>
                          </div>
                          <ScoreBar value={normTTFT} />
                        </div>
                      </div>

                      {/* Justification */}
                      {m.justification && (
                        <p className="text-[11px] text-slate-500 leading-relaxed border-t border-white/[0.05] pt-2.5">
                          {m.justification}
                        </p>
                      )}

                      {/* Badges */}
                      <div className="flex flex-wrap gap-1.5">
                        <LicenseBadge type={m.metrics.license} />
                        {modelEntry && <SourceBadge source={modelEntry.source} />}
                        {modelEntry?.is_new && (
                          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium border bg-cyan-500/10 text-cyan-400 border-cyan-500/20 uppercase tracking-wide">
                            <Sparkles className="w-2.5 h-2.5" /> New
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
            </div>
          </div>

          {/* ── RIGHT: Models Table ── */}
          <div className="xl:col-span-3 space-y-5">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-white flex items-center gap-2">
                <Database className="w-4 h-4 text-cyan-400" />
                All Models
                {!loadingModels && (
                  <span className="text-slate-500 font-normal">
                    ({filtered.length})
                  </span>
                )}
              </h2>
            </div>

            {/* Search + filter bar */}
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500 pointer-events-none" />
                <input
                  type="text"
                  placeholder="Search models…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="w-full h-9 pl-9 pr-3 text-sm bg-white/[0.04] border border-white/[0.08] rounded-lg text-slate-200 placeholder-slate-600 focus:outline-none focus:border-cyan-500/40 focus:bg-white/[0.06] transition-colors"
                />
              </div>
              <select
                value={srcFilter}
                onChange={(e) => setSrcFilter(e.target.value)}
                className="h-9 px-3 text-xs bg-white/[0.04] border border-white/[0.08] rounded-lg text-slate-300 focus:outline-none focus:border-cyan-500/40 cursor-pointer appearance-none"
              >
                <option value="all">All sources</option>
                <option value="huggingface">HuggingFace</option>
                <option value="artificial_analysis">Artif. Analysis</option>
                <option value="llm_stats">LLM Stats</option>
              </select>
            </div>

            {/* Table */}
            <div className="rounded-xl border border-white/[0.06] overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-white/[0.06] bg-white/[0.02]">
                      {[
                        { key: "name",               label: "Model",    sortable: false },
                        { key: "intelligence_score",  label: "IQ",       sortable: true  },
                        { key: "price_input",         label: "$/1M in",  sortable: true  },
                        { key: "speed_tps",           label: "Speed",    sortable: true  },
                        { key: "ttft_ms",             label: "TTFT",     sortable: true  },
                        { key: "context_window",      label: "Context",  sortable: true  },
                      ].map((col) => (
                        <th
                          key={col.key}
                          onClick={col.sortable ? () => toggleSort(col.key) : undefined}
                          className={`px-3 py-2.5 text-left text-[10px] font-semibold text-slate-500 uppercase tracking-widest whitespace-nowrap
                            ${col.sortable ? "cursor-pointer hover:text-slate-300 transition-colors select-none" : ""}`}
                        >
                          <div className="flex items-center gap-1">
                            {col.label}
                            {col.sortable &&
                              (sortField === col.key ? (
                                sortDir === "desc" ? (
                                  <ChevronDown className="w-3 h-3 text-cyan-400" />
                                ) : (
                                  <ChevronUp className="w-3 h-3 text-cyan-400" />
                                )
                              ) : (
                                <ChevronDown className="w-3 h-3 opacity-20" />
                              ))}
                          </div>
                        </th>
                      ))}
                      <th className="px-3 py-2.5 text-left text-[10px] font-semibold text-slate-500 uppercase tracking-widest">
                        Src
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {loadingModels
                      ? Array.from({ length: 10 }).map((_, i) => (
                          <tr key={i} className="border-b border-white/[0.04]">
                            {Array.from({ length: 7 }).map((_, j) => (
                              <td key={j} className="px-3 py-3">
                                <div
                                  className="h-3 rounded bg-white/[0.05] animate-pulse"
                                  style={{ width: `${40 + ((i * 7 + j) % 5) * 10}%` }}
                                />
                              </td>
                            ))}
                          </tr>
                        ))
                      : filtered.slice(0, 25).map((m, i) => (
                          <tr
                            key={m.name}
                            className={`border-b border-white/[0.04] transition-colors
                              ${i % 2 === 0 ? "" : "bg-white/[0.01]"}
                              hover:bg-cyan-500/[0.04]`}
                          >
                            {/* Model name */}
                            <td className="px-3 py-2.5 max-w-[200px]">
                              <div className="flex items-center gap-1.5">
                                <div className="min-w-0">
                                  <p className="font-medium text-slate-200 truncate leading-tight">{m.name}</p>
                                  <p className="text-[10px] text-slate-600 leading-tight mt-0.5">{m.provider ?? "—"}</p>
                                </div>
                                {m.is_new && (
                                  <Sparkles className="w-3 h-3 text-cyan-400 flex-shrink-0" />
                                )}
                              </div>
                            </td>
                            {/* IQ */}
                            <td className="px-3 py-2.5">
                              <span
                                className={`tabular-nums font-semibold ${
                                  (m.intelligence_score ?? 0) >= 80
                                    ? "text-cyan-400"
                                    : (m.intelligence_score ?? 0) >= 60
                                    ? "text-slate-200"
                                    : "text-slate-500"
                                }`}
                              >
                                {fmt(m.intelligence_score)}
                              </span>
                            </td>
                            {/* Price */}
                            <td className="px-3 py-2.5 tabular-nums text-slate-400">
                              {fmtPrice(m.price_input)}
                            </td>
                            {/* Speed */}
                            <td className="px-3 py-2.5 tabular-nums text-slate-400">
                              {m.speed_tps != null ? `${fmt(m.speed_tps, 0)}` : "—"}
                            </td>
                            {/* TTFT */}
                            <td className="px-3 py-2.5 tabular-nums text-slate-400">
                              {m.ttft_ms != null ? `${fmt(m.ttft_ms, 0)}ms` : "—"}
                            </td>
                            {/* Context */}
                            <td className="px-3 py-2.5 tabular-nums text-slate-400">
                              {fmtCtx(m.context_window)}
                            </td>
                            {/* Source */}
                            <td className="px-3 py-2.5">
                              <SourceBadge source={m.source} />
                            </td>
                          </tr>
                        ))}
                  </tbody>
                </table>
              </div>
              {!loadingModels && filtered.length > 25 && (
                <div className="px-4 py-2.5 border-t border-white/[0.06] bg-white/[0.01]">
                  <p className="text-xs text-slate-600">
                    Showing 25 of {filtered.length} models
                  </p>
                </div>
              )}
              {!loadingModels && filtered.length === 0 && (
                <div className="py-12 text-center text-sm text-slate-600">
                  No models match your search.
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ──────────────── NEW MODELS BANNER ──────────────── */}
        {!loadingModels && newModels.length > 0 && (
          <div className="rounded-xl border border-cyan-500/20 bg-gradient-to-r from-cyan-500/[0.05] to-blue-600/[0.03] p-5">
            <div className="flex items-center gap-2.5 mb-4">
              <div className="w-7 h-7 rounded-lg bg-cyan-500/15 flex items-center justify-center">
                <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-white">
                  {newModels.length} New Model{newModels.length > 1 ? "s" : ""} Detected
                </h2>
                <p className="text-xs text-slate-500">First seen in latest collection run</p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              {newModels.map((m) => (
                <div
                  key={m.name}
                  className="flex items-center gap-2 px-3 py-2 rounded-lg border border-cyan-500/20 bg-cyan-500/[0.05] text-xs"
                >
                  <span className="font-medium text-cyan-200">{m.name}</span>
                  <span className="text-slate-700">·</span>
                  <LicenseBadge type={m.license_type} />
                  <SourceBadge source={m.source} />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ──────────────── SCORING INFO ──────────────── */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[
            {
              icon: Brain,
              title: "AHP Weighting",
              body: "Analytic Hierarchy Process derives consistent pairwise weights per profile (CR < 0.10).",
            },
            {
              icon: BarChart3,
              title: "TOPSIS Scoring",
              body: "Models ranked by Euclidean distance to the ideal positive/negative solution.",
            },
            {
              icon: Shield,
              title: "Compliance Filter",
              body: "Enable 'Commercial only' to exclude non-commercial & restrictive license models.",
            },
          ].map(({ icon: Icon, title, body }) => (
            <div
              key={title}
              className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4 space-y-2"
            >
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg bg-white/[0.04] flex items-center justify-center">
                  <Icon className="w-3.5 h-3.5 text-slate-500" />
                </div>
                <p className="text-sm font-medium text-slate-200">{title}</p>
              </div>
              <p className="text-xs text-slate-500 leading-relaxed">{body}</p>
            </div>
          ))}
        </div>

        {/* ──────────────── FOOTER ──────────────── */}
        <footer className="border-t border-white/[0.05] pt-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 text-xs text-slate-700">
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded-sm bg-gradient-to-br from-cyan-400 to-blue-600 flex items-center justify-center">
              <BarChart3 className="w-2.5 h-2.5 text-white" />
            </div>
            <span>EPINEON AI · LLM Monitor v1.0</span>
            <span className="text-slate-800">·</span>
            <span>AHP+TOPSIS · Multi-Criteria Decision Analysis</span>
          </div>
          <span>PFE Challenge 2026 — ESITH Cohort</span>
        </footer>
      </main>
    </div>
  );
}
