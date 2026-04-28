"use client"

import { useState } from "react"
import { CommandHeader } from "@/components/command-header"
import { ActivityFeed } from "@/components/activity-feed"
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
        {/* Left: Activity Feed */}
        <aside className="hidden lg:flex w-80 shrink-0 flex-col border-r border-border bg-card">
          <ActivityFeed />
        </aside>

        {/* Center: Lead Pipeline */}
        <main className="flex flex-1 flex-col overflow-hidden bg-background">
          <LeadPipeline
            selectedLead={selectedLead}
            onSelectLead={setSelectedLead}
            refreshTrigger={refreshTrigger}
          />
        </main>

        {/* Right: Co-pilot Sidebar */}
        <aside
          className={cn(
            "shrink-0 flex-col border-l border-border bg-card transition-all duration-300",
            selectedLead
              ? "w-80 xl:w-96 flex"
              : "w-0 lg:w-80 lg:flex overflow-hidden"
          )}
        >
          <CopilotSidebar
            lead={selectedLead}
            onClose={() => setSelectedLead(null)}
          />
        </aside>
      </div>

      {/* Mobile bottom bar for activity indicator */}
      <div className="lg:hidden fixed bottom-4 left-4 right-4 flex items-center justify-between rounded-xl bg-card border border-border px-4 py-3 shadow-lg">
        <div className="flex items-center gap-2">
          <div className="size-2 rounded-full bg-primary animate-pulse" />
          <span className="text-xs text-muted-foreground">
            AI working in background
          </span>
        </div>
        <button
          onClick={() => setSelectedLead(null)}
          className={cn(
            "text-xs font-medium text-primary",
            !selectedLead && "opacity-50"
          )}
        >
          {selectedLead ? "Close Panel" : "Select Lead"}
        </button>
      </div>
    </div>
  )
}
