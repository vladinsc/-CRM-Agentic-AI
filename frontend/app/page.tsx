"use client"

import { useState } from "react"
import { CommandHeader } from "@/components/command-header"
import { ActivityFeed } from "@/components/activity-feed"
import { ScrapeJobsPanel } from "@/components/scrape-jobs-panel"
import { LeadPipeline, type Lead } from "@/components/lead-pipeline"
import { CopilotSidebar } from "@/components/copilot-sidebar"
import { cn } from "@/lib/utils"
import { useAuth } from "@/hooks/useAuth"

export default function AgenticCommandCenter() {
  const { loading } = useAuth()
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null)
  const [refreshTrigger, setRefreshTrigger] = useState(0)

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-950">
        <div className="size-6 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin" />
      </div>
    )
  }

  return (
    <div className="flex h-screen flex-col bg-background">
      <CommandHeader onLeadCreated={() => setRefreshTrigger((n) => n + 1)} />

      <div className="flex flex-1 overflow-hidden">
        {/* Left: Activity Feed + Scraping jobs */}
        <aside className="hidden xl:flex w-80 shrink-0 flex-col border-r border-border bg-card overflow-hidden">
          <div className="flex-1 overflow-hidden">
            <ActivityFeed />
          </div>
          <ScrapeJobsPanel refreshTrigger={refreshTrigger} />
        </aside>

        {/* Center: Lead Pipeline — hidden on mobile when copilot is open */}
        <main className={cn(
          "flex flex-1 flex-col overflow-hidden bg-background",
          selectedLead && "hidden lg:flex"
        )}>
          <LeadPipeline
            selectedLead={selectedLead}
            onSelectLead={setSelectedLead}
            refreshTrigger={refreshTrigger}
          />
        </main>

        {/* Right: Co-pilot Sidebar — full screen on mobile when open */}
        <aside
          className={cn(
            "flex-col border-l border-border bg-card overflow-hidden transition-all duration-300",
            selectedLead
              ? "flex w-full lg:w-80 lg:shrink-0 xl:w-96"
              : "hidden lg:flex lg:w-80 lg:shrink-0"
          )}
        >
          <CopilotSidebar
            lead={selectedLead}
            onClose={() => setSelectedLead(null)}
          />
        </aside>
      </div>

      {/* Mobile bottom bar — only when no lead selected (copilot is closed) */}
      {!selectedLead && (
        <div className="lg:hidden fixed bottom-4 left-4 right-4 flex items-center gap-2 rounded-xl bg-card border border-border px-4 py-3 shadow-lg">
          <div className="size-2 rounded-full bg-primary animate-pulse shrink-0" />
          <span className="text-xs text-muted-foreground">
            AI working in background
          </span>
        </div>
      )}
    </div>
  )
}
