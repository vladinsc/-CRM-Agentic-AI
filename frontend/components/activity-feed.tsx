"use client"

import { useEffect, useState, useCallback } from "react"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"
import {
  Search,
  Mail,
  FileText,
  Phone,
  Sparkles,
  CheckCircle2,
  Clock,
  Brain,
  RefreshCw,
} from "lucide-react"
import { api, type ActivityAPI } from "@/lib/api"

interface Activity {
  id: string
  type: "research" | "email" | "analysis" | "call" | "insight"
  message: string
  leadName?: string
  timestamp: Date
  status: "completed" | "in-progress"
}

const activityIcons = {
  research: Search,
  email: Mail,
  analysis: FileText,
  call: Phone,
  insight: Brain,
}

// Mapează action_type-uri din backend la tipuri din UI
function normalizeType(type: string): Activity["type"] {
  const map: Record<string, Activity["type"]> = {
    research: "research",
    email: "email",
    analysis: "analysis",
    call: "call",
    insight: "insight",
  }
  return map[type] ?? "research"
}

function fromAPI(a: ActivityAPI): Activity {
  return {
    id: String(a.id),
    type: normalizeType(a.type),
    message: a.message,
    leadName: a.leadName,
    timestamp: new Date(a.timestamp),
    status: a.status as Activity["status"],
  }
}

function formatTimeAgo(date: Date): string {
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000)
  if (seconds < 60) return "now"
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  return `${hours}h ago`
}

export function ActivityFeed() {
  const [activities, setActivities] = useState<Activity[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  const fetchActivities = useCallback(async () => {
    try {
      const data = await api.getActivity(10)
      setActivities(data.map(fromAPI))
      setError(false)
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchActivities()
    // Refresh la fiecare 30s pentru a prinde activități noi
    const interval = setInterval(fetchActivities, 30_000)
    return () => clearInterval(interval)
  }, [fetchActivities])

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <div className="flex size-7 items-center justify-center rounded-md bg-primary/10">
          <Sparkles className="size-4 text-primary" />
        </div>
        <div>
          <h2 className="text-sm font-semibold text-foreground">AI Activity</h2>
          <p className="text-xs text-muted-foreground">Working autonomously</p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={fetchActivities}
            className="rounded p-1 text-muted-foreground hover:text-foreground transition-colors"
            title="Refresh"
          >
            <RefreshCw className="size-3.5" />
          </button>
          <Badge variant="outline" className="border-primary/30 text-primary">
            <span className="mr-1.5 inline-block size-1.5 animate-pulse rounded-full bg-primary" />
            Live
          </Badge>
        </div>
      </div>

      <ScrollArea className="flex-1">
        <div className="space-y-1 p-2">
          {loading && (
            // Skeleton loader
            Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="rounded-lg p-3">
                <div className="flex items-start gap-3">
                  <div className="size-8 rounded-md bg-secondary animate-pulse" />
                  <div className="flex-1 space-y-2">
                    <div className="h-3 w-3/4 rounded bg-secondary animate-pulse" />
                    <div className="h-2 w-1/2 rounded bg-secondary animate-pulse" />
                  </div>
                </div>
              </div>
            ))
          )}

          {!loading && error && (
            <div className="flex flex-col items-center gap-2 py-8 text-center">
              <p className="text-xs text-muted-foreground">
                Could not load activity
              </p>
              <button
                onClick={fetchActivities}
                className="text-xs text-primary hover:underline"
              >
                Try again
              </button>
            </div>
          )}

          {!loading && !error && activities.length === 0 && (
            <div className="flex flex-col items-center gap-2 py-8 text-center">
              <Clock className="size-8 text-muted-foreground/30" />
              <p className="text-xs text-muted-foreground">
                No activity yet — research a lead to get started
              </p>
            </div>
          )}

          {!loading && !error && activities.map((activity, index) => {
            const Icon = activityIcons[activity.type] ?? Search
            return (
              <div
                key={activity.id}
                className="group rounded-lg p-3 transition-colors hover:bg-accent/50"
                style={{ animationDelay: `${index * 50}ms` }}
              >
                <div className="flex items-start gap-3">
                  <div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-secondary">
                    <Icon className="size-4 text-muted-foreground group-hover:text-foreground transition-colors" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <p className="text-sm text-foreground">{activity.message}</p>
                      <CheckCircle2 className="size-3.5 text-primary shrink-0" />
                    </div>
                    {activity.leadName && (
                      <p className="mt-0.5 truncate text-xs text-muted-foreground">
                        {activity.leadName}
                      </p>
                    )}
                    <p className="mt-1 text-xs text-muted-foreground/70">
                      {formatTimeAgo(activity.timestamp)}
                    </p>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </ScrollArea>
    </div>
  )
}
