"use client"

import { useEffect, useState, useCallback } from "react"
import { Loader2, CheckCircle2, XCircle, Search, RefreshCw, Ban } from "lucide-react"
import { toast } from "sonner"
import { api, type ScrapeJobAPI } from "@/lib/api"

interface ScrapeJobsPanelProps {
  /** Bumped by the parent when a scrape may have produced new leads. */
  refreshTrigger?: number
}

function statusMeta(status: ScrapeJobAPI["status"]) {
  switch (status) {
    case "running":
    case "pending":
      return { label: "Running", cls: "text-blue-400", icon: Loader2, spin: true }
    case "completed":
      return { label: "Completed", cls: "text-green-400", icon: CheckCircle2, spin: false }
    case "failed":
      return { label: "Failed", cls: "text-red-400", icon: XCircle, spin: false }
    case "cancelled":
      return { label: "Cancelled", cls: "text-muted-foreground", icon: Ban, spin: false }
    default:
      return { label: status, cls: "text-muted-foreground", icon: Search, spin: false }
  }
}

// Sales Nav URLs are long; show a short, human label for the query.
function queryLabel(query: string): string {
  if (!query) return "Sales Navigator search"
  try {
    const u = new URL(query)
    if (u.hostname.includes("linkedin.com")) {
      const kw = u.searchParams.get("keywords")
      return kw ? `“${kw}”` : "Sales Navigator search"
    }
  } catch {
    // not a URL — it's a plain query string
  }
  return query.length > 48 ? query.slice(0, 48) + "…" : query
}

export function ScrapeJobsPanel({ refreshTrigger }: ScrapeJobsPanelProps) {
  const [jobs, setJobs] = useState<ScrapeJobAPI[]>([])
  const [loaded, setLoaded] = useState(false)

  const fetchJobs = useCallback(async () => {
    try {
      const data = await api.listScrapeJobs()
      setJobs(data)
    } catch {
      // ignore transient errors
    } finally {
      setLoaded(true)
    }
  }, [])

  const cancelJob = useCallback(async (jobId: number) => {
    try {
      await api.cancelScrapeJob(jobId)
      toast.info("Scrape cancelled", { description: "Leads found so far are kept." })
      fetchJobs()
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to cancel"
      toast.error("Couldn't cancel", { description: msg })
    }
  }, [fetchJobs])

  // Poll while any job is active, otherwise just refresh occasionally.
  useEffect(() => {
    fetchJobs()
    const id = setInterval(fetchJobs, 3000)
    return () => clearInterval(id)
  }, [fetchJobs, refreshTrigger])

  if (loaded && jobs.length === 0) return null

  return (
    <div className="border-t border-border">
      <div className="flex items-center justify-between px-4 py-2.5">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wide">
          <Search className="size-3.5" />
          Scraping jobs
        </div>
        <button
          onClick={fetchJobs}
          className="text-muted-foreground hover:text-foreground transition-colors"
          title="Refresh"
        >
          <RefreshCw className="size-3.5" />
        </button>
      </div>

      <div className="max-h-56 overflow-y-auto px-2 pb-2 space-y-1.5">
        {jobs.map((job) => {
          const m = statusMeta(job.status)
          const Icon = m.icon
          return (
            <div
              key={job.id}
              className="rounded-lg border border-border bg-muted/20 px-3 py-2 space-y-1"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-medium truncate">{queryLabel(job.query)}</span>
                <div className="flex items-center gap-2 shrink-0">
                  <span className={`flex items-center gap-1 text-[11px] font-medium ${m.cls}`}>
                    <Icon className={`size-3 ${m.spin ? "animate-spin" : ""}`} />
                    {m.label}
                  </span>
                  {(job.status === "running" || job.status === "pending") && (
                    <button
                      onClick={() => cancelJob(job.id)}
                      title="Cancel scrape"
                      className="text-muted-foreground hover:text-red-400 transition-colors"
                    >
                      <Ban className="size-3.5" />
                    </button>
                  )}
                </div>
              </div>
              <div className="text-[11px] text-muted-foreground">
                {job.scraped_count} scraped · <span className="text-green-400">{job.leads_created} matched ICP</span>
                {job.scraped_count > job.leads_created && (
                  <> · {job.scraped_count - job.leads_created} skipped</>
                )}
              </div>
              {job.status === "failed" && job.error_message && (
                <div className="text-[11px] text-red-400/90">{job.error_message}</div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
