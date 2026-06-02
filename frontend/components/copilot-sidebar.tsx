"use client"

import { useState, useEffect } from "react"
import type { Lead } from "@/components/lead-pipeline"
import { api, type CopilotAPI } from "@/lib/api"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"
import {
  Wand2,
  Copy,
  Send,
  Phone,
  Mail,
  Building2,
  User,
  Target,
  MessageSquare,
  CheckCircle2,
  Sparkles,
  X,
  ChevronRight,
  RefreshCw,
  ExternalLink,
} from "lucide-react"

interface CopilotSidebarProps {
  lead: Lead | null
  onClose: () => void
}

export function CopilotSidebar({ lead, onClose }: CopilotSidebarProps) {
  const [copilot, setCopilot] = useState<CopilotAPI | null>(null)
  const [loading, setLoading] = useState(false)
  const [regenerating, setRegenerating] = useState(false)
  const [sending, setSending] = useState(false)
  const [copiedEmail, setCopiedEmail] = useState(false)
  const [activeTab, setActiveTab] = useState<"argument" | "message">("argument")

  useEffect(() => {
    if (!lead) {
      setCopilot(null)
      return
    }
    setCopilot(null)
    setLoading(true)

    // `cancelled` previne race condition-ul: dacă userul schimbă lead-ul
    // înainte ca un request in-flight să se termine, ignorăm răspunsul vechi.
    let cancelled = false
    let attempts = 0
    const MAX_ATTEMPTS = 30   // 30 × 3s = 90s max
    const INTERVAL_MS = 3000

    const fetchCopilot = () => {
      api.getCopilot(Number(lead.id))
        .then((data) => {
          if (cancelled) return  // lead s-a schimbat între timp — ignorăm
          if (data?.winning_argument) {
            setCopilot(data)
            setLoading(false)
          } else {
            attempts++
            if (attempts < MAX_ATTEMPTS) {
              setTimeout(fetchCopilot, INTERVAL_MS)
            } else {
              setCopilot(data)
              setLoading(false)
            }
          }
        })
        .catch(() => {
          if (cancelled) return
          setCopilot(null)
          setLoading(false)
        })
    }

    fetchCopilot()

    return () => {
      cancelled = true  // orice request in-flight va fi ignorat
    }
  }, [lead?.id])

  const handleRegenerate = async () => {
    if (!lead) return
    setRegenerating(true)
    try {
      const result = await api.regenerateCopilot(Number(lead.id))
      setCopilot(result)
      toast.success("Co-pilot insights updated")
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to regenerate insights"
      toast.error("Update failed", { description: msg })
    } finally {
      setRegenerating(false)
    }
  }

  const handleCopyEmail = () => {
    if (copilot?.draft_message) {
      navigator.clipboard.writeText(copilot.draft_message)
      setCopiedEmail(true)
      setTimeout(() => setCopiedEmail(false), 2000)
    }
  }

  const hasRealEmail = !!lead?.email && !lead.email.endsWith("@placeholder.invalid")

  const handleEditInGmail = () => {
    if (!lead || !copilot?.draft_message) return
    if (!hasRealEmail) {
      toast.error("No email address", { description: "This scraped lead has no email captured." })
      return
    }
    const subject = `Following up — ${lead.company}`
    const url = `https://mail.google.com/mail/?view=cm&to=${encodeURIComponent(lead.email)}&su=${encodeURIComponent(subject)}&body=${encodeURIComponent(copilot.draft_message)}`
    window.open(url, "_blank")
  }

  const handleSendEmail = async () => {
    if (!lead) return
    if (!hasRealEmail) {
      toast.error("No email address", { description: "This scraped lead has no email captured." })
      return
    }
    setSending(true)
    try {
      await api.sendCopilotEmail(Number(lead.id))
      toast.success("Email sent", { description: `Sent to ${lead.email}` })
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to send email"
      toast.error("Send failed", { description: msg })
    } finally {
      setSending(false)
    }
  }

  if (!lead) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-6 text-center">
        <div className="flex size-16 items-center justify-center rounded-2xl bg-secondary mb-4">
          <Wand2 className="size-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold text-foreground">
          AI Co-pilot Ready
        </h3>
        <p className="mt-2 text-sm text-muted-foreground max-w-[200px]">
          Select a lead from the pipeline to get personalized insights and ready-to-send messages
        </p>
        <div className="mt-6 flex items-center gap-2 text-xs text-muted-foreground">
          <ChevronRight className="size-4" />
          <span>Click on any lead to start</span>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-0 flex-col animate-in slide-in-from-right-4">
      {/* Header */}
      <div className="border-b border-border px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="flex size-7 items-center justify-center rounded-md bg-primary/10">
              <Sparkles className="size-4 text-primary" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-foreground">Co-pilot</h2>
              <p className="text-xs text-muted-foreground">AI-powered insights</p>
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground"
          >
            <X className="size-4" />
          </Button>
        </div>
      </div>

      <ScrollArea className="flex-1 min-h-0">
        <div className="p-4 space-y-4">
          {/* Lead info card */}
          <div className="rounded-lg border border-border bg-secondary/30 p-4">
            <div className="flex items-start gap-3">
              <div className="flex size-12 items-center justify-center rounded-full bg-primary/20 text-primary font-semibold text-lg">
                {lead.name.split(" ").map((n) => n[0]).join("")}
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="font-semibold text-foreground truncate">{lead.name}</h3>
                <p className="text-sm text-muted-foreground">{lead.role}</p>
                <div className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Building2 className="size-3" />
                  <span className="truncate">{lead.company}</span>
                </div>
              </div>
              <Badge
                variant="outline"
                className={cn(
                  "font-mono text-sm font-bold shrink-0",
                  lead.score >= 80
                    ? "border-score-hot/50 text-score-hot"
                    : lead.score >= 60
                    ? "border-score-warm/50 text-score-warm"
                    : "border-score-cool/50 text-score-cool"
                )}
              >
                {lead.score}%
              </Badge>
            </div>

            {/* Quick actions */}
            <div className="mt-4 flex gap-2">
              <Button
                variant="outline"
                size="sm"
                className="flex-1 gap-1.5"
                onClick={() => window.open(`https://mail.google.com/mail/?view=cm&to=${encodeURIComponent(lead.email)}`)}
              >
                <Mail className="size-3.5" />
                Email
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="flex-1 gap-1.5"
                onClick={() => window.open(`tel:${lead.phone}`)}
              >
                <Phone className="size-3.5" />
                Call
              </Button>
            </div>
          </div>

          {/* Tabs */}
          <div className="flex rounded-lg bg-secondary/50 p-1 gap-1">
            <button
              onClick={() => setActiveTab("argument")}
              className={cn(
                "flex-1 rounded-md px-3 py-2 text-xs font-medium transition-all flex items-center justify-center gap-1.5",
                activeTab === "argument"
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <Target className="size-3.5" />
              Winning Argument
            </button>
            <button
              onClick={() => setActiveTab("message")}
              className={cn(
                "flex-1 rounded-md px-3 py-2 text-xs font-medium transition-all flex items-center justify-center gap-1.5",
                activeTab === "message"
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <MessageSquare className="size-3.5" />
              Draft Message
            </button>
          </div>

          {/* Content based on active tab */}
          {activeTab === "argument" ? (
            <div className="space-y-4">
              {/* Winning argument */}
              <div className="rounded-lg border border-primary/20 bg-primary/5 p-4">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Target className="size-4 text-primary" />
                    <span className="text-sm font-semibold text-foreground">
                      Winning Strategy
                    </span>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    onClick={handleRegenerate}
                    disabled={regenerating || loading}
                    className="text-muted-foreground hover:text-foreground"
                    title="Regenerate"
                  >
                    <RefreshCw className={cn("size-3.5", regenerating && "animate-spin")} />
                  </Button>
                </div>
                {loading ? (
                  <div className="space-y-2">
                    <Skeleton className="h-3 w-full" />
                    <Skeleton className="h-3 w-5/6" />
                    <Skeleton className="h-3 w-4/6" />
                  </div>
                ) : copilot?.winning_argument ? (
                  <p className="text-sm text-foreground leading-relaxed">
                    {copilot.winning_argument}
                  </p>
                ) : (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Sparkles className="size-4 shrink-0 text-primary/50" />
                    <span>
                      Research this lead first — the Co-pilot will generate a personalized winning argument.
                    </span>
                  </div>
                )}
              </div>

              {/* Signals breakdown */}
              <div>
                <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                  Buying Signals
                </h4>
                <div className="flex flex-wrap gap-2">
                  {lead.signals.map((signal) => (
                    <Badge
                      key={signal}
                      variant="secondary"
                      className="gap-1"
                    >
                      <CheckCircle2 className="size-3 text-primary" />
                      {signal}
                    </Badge>
                  ))}
                </div>
              </div>

              {/* Deal value */}
              <div className="rounded-lg bg-secondary/50 p-4">
                <div className="text-xs text-muted-foreground mb-1">
                  Estimated Deal Value
                </div>
                <div className="text-2xl font-bold text-foreground">{lead.value}</div>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Draft message */}
              <div className="rounded-lg border border-border bg-background p-4">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Mail className="size-4 text-primary" />
                    <span className="text-sm font-semibold text-foreground">
                      Personalized Email
                    </span>
                  </div>
                  <div className="flex items-center gap-1">
                    <Badge variant="outline" className="text-[10px]">
                      AI Generated
                    </Badge>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      onClick={handleRegenerate}
                      disabled={regenerating || loading}
                      className="text-muted-foreground hover:text-foreground"
                      title="Regenerate"
                    >
                      <RefreshCw className={cn("size-3.5", regenerating && "animate-spin")} />
                    </Button>
                  </div>
                </div>
                <div className="text-sm text-foreground whitespace-pre-line leading-relaxed bg-secondary/30 rounded-md p-3 font-mono text-xs min-h-[80px]">
                  {loading ? (
                    <div className="space-y-2">
                      <Skeleton className="h-3 w-full" />
                      <Skeleton className="h-3 w-5/6" />
                      <Skeleton className="h-3 w-full" />
                      <Skeleton className="h-3 w-3/4" />
                      <Skeleton className="h-3 w-5/6" />
                    </div>
                  ) : copilot?.draft_message ? (
                    copilot.draft_message
                  ) : (
                    <span className="text-muted-foreground not-italic font-sans">
                      No draft yet — research this lead to generate a personalized email.
                    </span>
                  )}
                </div>
              </div>

              {/* Action buttons */}
              <div className="flex flex-col gap-2">
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    className="flex-1 gap-2"
                    onClick={handleCopyEmail}
                    disabled={!copilot?.draft_message}
                  >
                    {copiedEmail ? (
                      <>
                        <CheckCircle2 className="size-4 text-primary" />
                        Copied!
                      </>
                    ) : (
                      <>
                        <Copy className="size-4" />
                        Copy
                      </>
                    )}
                  </Button>
                  <Button
                    variant="outline"
                    className="flex-1 gap-2"
                    onClick={handleEditInGmail}
                    disabled={!copilot?.draft_message}
                  >
                    <ExternalLink className="size-4" />
                    Edit in Gmail
                  </Button>
                </div>
                <Button
                  className="w-full gap-2"
                  disabled={!copilot?.draft_message || sending}
                  onClick={handleSendEmail}
                >
                  {sending ? (
                    <>
                      <RefreshCw className="size-4 animate-spin" />
                      Sending...
                    </>
                  ) : (
                    <>
                      <Send className="size-4" />
                      Send Email
                    </>
                  )}
                </Button>
              </div>
            </div>
          )}

          {/* Contact details */}
          <div className="pt-2">
            <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
              Contact Details
            </h4>
            <div className="space-y-2">
              <div className="flex items-center gap-3 text-sm">
                <Mail className="size-4 text-muted-foreground" />
                <span className="text-foreground truncate">
                  {lead.email?.endsWith("@placeholder.invalid")
                    ? "No email captured"
                    : lead.email}
                </span>
              </div>
              <div className="flex items-center gap-3 text-sm">
                <Phone className="size-4 text-muted-foreground" />
                <span className="text-foreground">{lead.phone || "—"}</span>
              </div>
              <div className="flex items-center gap-3 text-sm">
                <User className="size-4 text-muted-foreground" />
                <span className="text-foreground">{lead.role}</span>
              </div>
            </div>
          </div>
        </div>
      </ScrollArea>
    </div>
  )
}
