"use client"

import { useState } from "react"
import { toast } from "sonner"
import {
  X,
  AlertCircle,
  Loader2,
  Linkedin,
  Sparkles,
  Search,
  ChevronRight,
  Chrome,
} from "lucide-react"
import { api, type SearchQuerySuggestion } from "@/lib/api"

interface LinkedInScraperModalProps {
  open: boolean
  onClose: () => void
  onSuccess: () => void
}

type Tab = "extension" | "suggest"

export function LinkedInScraperModal({ open, onClose }: LinkedInScraperModalProps) {
  const [tab, setTab] = useState<Tab>("extension")

  // Suggest tab
  const [suggestLoading, setSuggestLoading] = useState(false)
  const [suggestions, setSuggestions] = useState<SearchQuerySuggestion[]>([])
  const [suggestError, setSuggestError] = useState<string | null>(null)

  function handleClose() {
    setSuggestError(null)
    onClose()
  }

  async function handleSuggest() {
    setSuggestLoading(true)
    setSuggestError(null)
    setSuggestions([])
    try {
      const result = await api.suggestSearchQueries()
      setSuggestions(result.queries)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Agent failed"
      setSuggestError(msg)
      toast.error("AI agent failed", { description: msg })
    } finally {
      setSuggestLoading(false)
    }
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-card border border-border rounded-lg shadow-lg w-full max-w-lg max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-border shrink-0">
          <div className="flex items-center gap-2">
            <Linkedin className="size-5 text-[#0A66C2]" />
            <h2 className="text-lg font-semibold">Find Leads</h2>
          </div>
          <button onClick={handleClose} className="p-1 hover:bg-accent rounded-md transition-colors">
            <X className="size-4" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-border shrink-0">
          {(["extension", "suggest"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`flex-1 px-3 py-2.5 text-xs font-medium transition-colors capitalize ${
                tab === t
                  ? "border-b-2 border-primary text-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {t === "extension" && "Browser Extension"}
              {t === "suggest" && "AI Suggest"}
            </button>
          ))}
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">

          {/* ── Extension Tab ── */}
          {tab === "extension" && (
            <div className="space-y-4">
              <div className="p-3 rounded-lg border border-primary/30 bg-primary/10 space-y-1.5">
                <p className="text-sm font-medium flex items-center gap-1.5">
                  <Chrome className="size-4 text-primary" />
                  Scrape leads with the browser extension
                </p>
                <p className="text-xs text-muted-foreground">
                  Leads are scraped inside your own logged-in LinkedIn tab — your session
                  stays safe — and only leads matching your{" "}
                  <strong>Ideal Customer Profile</strong> are added to the pipeline.
                </p>
              </div>

              <ol className="text-xs text-muted-foreground space-y-2 list-decimal list-inside">
                <li>
                  Load the <strong>CRM Lead Scraper</strong> extension (Chrome →
                  <code className="text-[11px] bg-muted px-1 rounded mx-1">chrome://extensions</code>
                  → Developer mode → Load unpacked → select the <code className="text-[11px] bg-muted px-1 rounded">extension/</code> folder).
                </li>
                <li>Make sure you've set up your ICP first — scraping is blocked without one.</li>
                <li>
                  <strong>On a page:</strong> open a LinkedIn Sales Navigator search, click the
                  extension → <em>Scrape this search</em>.
                </li>
                <li>
                  <strong>Autonomous:</strong> paste a Sales Navigator search URL into the
                  extension and click <em>Auto-scrape from URL</em> — it scrapes in the background.
                </li>
              </ol>

              <p className="text-xs text-muted-foreground">
                Matched leads land in your Intent Pipeline and AI research runs on each automatically.
              </p>
            </div>
          )}

          {/* ── Suggest Tab ── */}
          {tab === "suggest" && (
            <div className="space-y-4">
              <p className="text-xs text-muted-foreground">
                The AI analyzes your existing leads and suggests targeted LinkedIn Sales Navigator
                search queries to find similar high-intent prospects.
              </p>

              <button
                onClick={handleSuggest}
                disabled={suggestLoading}
                className="w-full h-10 bg-primary text-primary-foreground hover:bg-primary/90 rounded-md text-sm font-medium transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {suggestLoading ? (
                  <><Loader2 className="size-4 animate-spin" /> Analyzing leads…</>
                ) : (
                  <><Sparkles className="size-4" /> Suggest Search Queries</>
                )}
              </button>

              {suggestError && (
                <p className="text-sm text-destructive flex items-center gap-1.5">
                  <AlertCircle className="size-4 shrink-0" />
                  {suggestError}
                </p>
              )}

              {suggestions.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs font-medium text-muted-foreground">
                    {suggestions.length} queries suggested
                  </p>
                  {suggestions.map((s, i) => (
                    <div
                      key={i}
                      className="p-3 rounded-lg border border-border bg-muted/20 space-y-1.5"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="space-y-0.5">
                          <p className="text-sm font-medium font-mono">{s.query}</p>
                          <p className="text-xs text-muted-foreground">{s.expected_title}</p>
                        </div>
                        <Search className="size-4 text-muted-foreground shrink-0 mt-0.5" />
                      </div>
                      <p className="text-xs text-muted-foreground">{s.reasoning}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
