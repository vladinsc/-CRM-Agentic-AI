"use client";

import { useState, useEffect, useCallback } from "react"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  TrendingUp,
  Building2,
  Flame,
  Zap,
  Snowflake,
  ArrowUpRight,
  RefreshCw,
  Plus,
} from "lucide-react"
import { api, type LeadAPI } from "@/lib/api"
import { toast } from "sonner"

// ── Lead interface (shared with Copilot sidebar) ─────────────────────────────

export interface Lead {
  id: string
  name: string
  company: string
  role: string
  email: string
  phone: string
  score: number
  value: string
  lastActivity: string
  signals: string[]
  // Copilot fields — rămân goale până la EPIC 6
  winningArgument: string
  draftMessage: string
}

// ── Mapare API → Lead UI ──────────────────────────────────────────────────────

function fromAPI(l: LeadAPI): Lead {
  return {
    id: String(l.id),
    name: l.name,
    company: l.company,
    role: l.role,
    email: l.email,
    phone: l.phone ?? "",
    score: l.score ?? 0,
    value: l.deal_value_display ?? "—",
    lastActivity: l.last_activity_description ?? "No activity yet",
    signals: l.signals ?? [],
    winningArgument: "",
    draftMessage: "",
  }
}

// ── Score helpers ─────────────────────────────────────────────────────────────

function getScoreColor(statusOrScore: string | number) {
  if (typeof statusOrScore === "string") {
    if (statusOrScore === "hot") return "text-score-hot"
    if (statusOrScore === "warm") return "text-score-warm"
    return "text-score-cool"
  }
  if (statusOrScore >= 80) return "text-score-hot"
  if (statusOrScore >= 60) return "text-score-warm"
  return "text-score-cool"
}

function getScoreBg(statusOrScore: string | number) {
  if (typeof statusOrScore === "string") {
    if (statusOrScore === "hot") return "bg-score-hot/10 border-score-hot/30"
    if (statusOrScore === "warm") return "bg-score-warm/10 border-score-warm/30"
    return "bg-score-cool/10 border-score-cool/30"
  }
  if (statusOrScore >= 80) return "bg-score-hot/10 border-score-hot/30"
  if (statusOrScore >= 60) return "bg-score-warm/10 border-score-warm/30"
  return "bg-score-cool/10 border-score-cool/30"
}

function getScoreIcon(statusOrScore: string | number) {
  if (typeof statusOrScore === "string") {
    if (statusOrScore === "hot") return Flame
    if (statusOrScore === "warm") return Zap
    return Snowflake
  }
  if (statusOrScore >= 80) return Flame
  if (statusOrScore >= 60) return Zap
  return Snowflake
}

// ── Component ─────────────────────────────────────────────────────────────────

interface LeadPipelineProps {
  selectedLead: Lead | null
  onSelectLead: (lead: Lead) => void
  refreshTrigger?: number
}

export function LeadPipeline({ selectedLead, onSelectLead, refreshTrigger }: LeadPipelineProps) {
  const [leads, setLeads] = useState<Lead[]>([])
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState(false)
  const [researchingId, setResearchingId] = useState<string | null>(null)
  const [researchError, setResearchError] = useState<string | null>(null)
  const [filter, setFilter] = useState<"all" | "hot" | "warm" | "cool">("all")

  const fetchLeads = useCallback(async () => {
    try {
      const data = await api.getLeads()
      setLeads(data.map(fromAPI))
      setFetchError(false)
    } catch {
      setFetchError(true)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchLeads()
  }, [fetchLeads, refreshTrigger])

  // Dacă lead-ul selectat a fost actualizat (ex. după research), sync-uiește selectedLead
  useEffect(() => {
    if (selectedLead) {
      const updated = leads.find((l) => l.id === selectedLead.id)
      if (updated && updated.score !== selectedLead.score) {
        onSelectLead(updated)
      }
    }
  }, [leads, selectedLead, onSelectLead])

  async function handleResearch(e: React.MouseEvent, leadId: string) {
    e.stopPropagation()
    setResearchingId(leadId)
    setResearchError(null)
    try {
      const updated = await api.researchLead(Number(leadId))
      const mapped = fromAPI(updated)
      setLeads((prev) => prev.map((l) => (l.id === leadId ? mapped : l)))
      toast.success(`Research complete — ${mapped.name}`, {
        description: `Intent score: ${mapped.score} · ${mapped.signals.length} signals detected`,
      })
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Research failed"
      setResearchError(msg)
      toast.error("Research failed", { description: msg })
    } finally {
      setResearchingId(null)
    }
  }

  const filteredLeads = leads.filter((lead) => {
    if (filter === "all") return true;
    if (filter === "hot") return lead.status === "hot";
    if (filter === "warm") return lead.status === "warm";
    return lead.status === "cool";
  });

  const stats = {
    hot: leads.filter((l) => l.status === "hot").length,
    warm: leads.filter((l) => l.status === "warm").length,
    cool: leads.filter((l) => l.status === "cool").length,
  };

  function getScoreColor(statusOrScore: string | number) {
    if (typeof statusOrScore === "string") {
      if (statusOrScore === "hot") return "text-score-hot";
      if (statusOrScore === "warm") return "text-score-warm";
      return "text-score-cool";
    }
    const score = Number(statusOrScore);
    if (score >= 80) return "text-score-hot";
    if (score >= 60) return "text-score-warm";
    return "text-score-cool";
  }

  function getScoreBg(statusOrScore: string | number) {
    if (typeof statusOrScore === "string") {
      if (statusOrScore === "hot") return "bg-score-hot/10 border-score-hot/30";
      if (statusOrScore === "warm")
        return "bg-score-warm/10 border-score-warm/30";
      return "bg-score-cool/10 border-score-cool/30";
    }
    const score = Number(statusOrScore);
    if (score >= 80) return "bg-score-hot/10 border-score-hot/30";
    if (score >= 60) return "bg-score-warm/10 border-score-warm/30";
    return "bg-score-cool/10 border-score-cool/30";
  }

  function getScoreIcon(statusOrScore: string | number) {
    if (typeof statusOrScore === "string") {
      if (statusOrScore === "hot") return Flame;
      if (statusOrScore === "warm") return Zap;
      return Snowflake;
    }
    const score = Number(statusOrScore);
    if (score >= 80) return Flame;
    if (score >= 60) return Zap;
    return Snowflake;
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="border-b border-border px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="flex size-7 items-center justify-center rounded-md bg-primary/10">
              <TrendingUp className="size-4 text-primary" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-foreground">
                Intent Pipeline
              </h2>
              <p className="text-xs text-muted-foreground">
                Sorted by closing probability
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={fetchLeads}
              className="rounded p-1 text-muted-foreground hover:text-foreground transition-colors"
              title="Refresh"
            >
              <RefreshCw className="size-3.5" />
            </button>
            <div className="flex items-center gap-1 text-xs">
              <span className="font-mono text-foreground">{leads.length}</span>
              <span className="text-muted-foreground">leads</span>
            </div>
          </div>
        </div>

        {/* Score filter tabs */}
        <div className="mt-3 flex gap-2">
          <button
            onClick={() => setFilter("all")}
            className={cn(
              "rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
              filter === "all"
                ? "bg-secondary text-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            All
          </button>
          <button
            onClick={() => setFilter("hot")}
            className={cn(
              "flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
              filter === "hot"
                ? "bg-score-hot/20 text-score-hot"
                : "text-muted-foreground hover:text-score-hot",
            )}
          >
            <Flame className="size-3" />
            Hot ({stats.hot})
          </button>
          <button
            onClick={() => setFilter("warm")}
            className={cn(
              "flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
              filter === "warm"
                ? "bg-score-warm/20 text-score-warm"
                : "text-muted-foreground hover:text-score-warm",
            )}
          >
            <Zap className="size-3" />
            Warm ({stats.warm})
          </button>
          <button
            onClick={() => setFilter("cool")}
            className={cn(
              "flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
              filter === "cool"
                ? "bg-score-cool/20 text-score-cool"
                : "text-muted-foreground hover:text-score-cool",
            )}
          >
            <Snowflake className="size-3" />
            Cool ({stats.cool})
          </button>
        </div>
      </div>

      {/* Lead list */}
      <ScrollArea className="flex-1">
        <div className="space-y-1 p-2">
          {/* Loading skeleton */}
          {loading &&
            Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="rounded-lg p-3">
                <div className="flex items-start gap-3">
                  <div className="size-10 rounded-lg bg-secondary animate-pulse" />
                  <div className="flex-1 space-y-2 pt-1">
                    <div className="h-3 w-1/2 rounded bg-secondary animate-pulse" />
                    <div className="h-2 w-3/4 rounded bg-secondary animate-pulse" />
                    <div className="h-2 w-2/3 rounded bg-secondary animate-pulse" />
                  </div>
                </div>
              </div>
            ))}

          {/* Fetch error state */}
          {!loading && fetchError && (
            <div className="flex flex-col items-center gap-2 py-12 text-center">
              <p className="text-sm text-muted-foreground">Could not load leads</p>
              <button
                onClick={fetchLeads}
                className="text-xs text-primary hover:underline"
              >
                Try again
              </button>
            </div>
          )}

          {/* Research error banner */}
          {researchError && (
            <div className="mx-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive flex items-center justify-between">
              <span>{researchError}</span>
              <button onClick={() => setResearchError(null)} className="ml-2 hover:opacity-70">✕</button>
            </div>
          )}

          {/* Empty state */}
          {!loading && !fetchError && leads.length === 0 && (
            <div className="flex flex-col items-center gap-3 py-12 text-center">
              <Plus className="size-10 text-muted-foreground/30" />
              <div>
                <p className="text-sm font-medium text-foreground">No leads yet</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Add your first lead to get started
                </p>
              </div>
            </div>
          )}

          {/* Lead cards */}
          {!loading && !fetchError &&
            filteredLeads.map((lead) => {
              const ScoreIcon = getScoreIcon(lead.status ?? lead.score)
              const isSelected = selectedLead?.id === lead.id
              const isResearching = researchingId === lead.id

              return (
                <button
                  key={lead.id}
                  onClick={() => onSelectLead(lead)}
                  className={cn(
                    "w-full rounded-lg p-3 text-left transition-all",
                    isSelected
                      ? "bg-primary/10 border border-primary/30"
                      : "hover:bg-accent/50 border border-transparent"
                  )}
                >
                  <div className="flex items-start gap-3">
                    {/* Score indicator */}
                    <div
                      className={cn(
                        "flex size-10 shrink-0 items-center justify-center rounded-lg border",
                        getScoreBg(lead.status ?? lead.score)
                      )}
                    >
                      <ScoreIcon
                        className={cn("size-5", getScoreColor(lead.status ?? lead.score))}
                      />
                    </div>

                    {/* Lead info */}
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-foreground truncate">
                          {lead.name}
                        </span>
                        <span
                          className={cn(
                            "font-mono text-sm font-bold",
                            lead.score === 0
                              ? "text-muted-foreground"
                              : getScoreColor(lead.status ?? lead.score)
                          )}
                        >
                          {lead.score === 0 ? "—" : `${lead.score}%`}
                        </span>
                      </div>
                      <div className="mt-0.5 flex items-center gap-1.5 text-xs text-muted-foreground">
                        <Building2 className="size-3" />
                        <span className="truncate">{lead.company}</span>
                        <span className="text-muted-foreground/50">•</span>
                        <span className="text-primary font-medium">
                          {lead.value}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground truncate">
                        {lead.lastActivity}
                      </p>
                      <div className="mt-2 flex flex-wrap items-center gap-1">
                        {lead.signals.map((signal) => (
                          <Badge
                            key={signal}
                            variant="outline"
                            className="text-[10px] px-1.5 py-0 h-5 border-border/50"
                          >
                            {signal}
                          </Badge>
                        ))}
                        {/* Research button — apare când nu e scor sau la hover */}
                        <button
                          onClick={(e) => handleResearch(e, lead.id)}
                          disabled={isResearching}
                          className={cn(
                            "ml-auto flex items-center gap-1 rounded-md px-2 py-0.5 text-[10px] font-medium transition-colors",
                            isResearching
                              ? "text-muted-foreground cursor-not-allowed"
                              : "text-primary hover:bg-primary/10"
                          )}
                        >
                          {isResearching ? (
                            <>
                              <RefreshCw className="size-3 animate-spin" />
                              Analyzing...
                            </>
                          ) : (
                            <>
                              <Flame className="size-3" />
                              Research
                            </>
                          )}
                        </button>
                      </div>
                    </div>

                    {/* Arrow indicator */}
                    <ArrowUpRight
                      className={cn(
                        "size-4 shrink-0 transition-all",
                        isSelected
                          ? "text-primary translate-x-0.5 -translate-y-0.5"
                          : "text-muted-foreground/50"
                      )}
                    />
                  </div>
                </button>
              )
            })}
        </div>
      </ScrollArea>
    </div>
  );
}

