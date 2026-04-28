"use client";

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Cpu,
  Bell,
  Settings,
  ChevronDown,
  Plus,
  Upload,
  LogOut,
  Github,
  Keyboard,
  Info,
} from "lucide-react"
import { api, type StatsAPI, type ActivityAPI } from "@/lib/api"
import { useAuth } from "@/hooks/useAuth"
import { AddLeadModal } from "@/components/add-lead-modal"
import { ImportCsvModal } from "@/components/import-csv-modal"

interface CommandHeaderProps {
  onLeadCreated?: () => void
}

export function CommandHeader({ onLeadCreated }: CommandHeaderProps) {
  const router = useRouter()
  const { user } = useAuth()
  const [open, setOpen] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [importOpen, setImportOpen] = useState(false)
  const [bellOpen, setBellOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [notifications, setNotifications] = useState<ActivityAPI[]>([])
  const [stats, setStats] = useState<StatsAPI | null>(null)

  useEffect(() => {
    api.getStats().then(setStats).catch(() => {})
    const interval = setInterval(() => {
      api.getStats().then(setStats).catch(() => {})
    }, 60_000)
    return () => clearInterval(interval)
  }, [])

  function handleBellOpen() {
    setBellOpen((o) => !o)
    setSettingsOpen(false)
    setOpen(false)
    // Fetch latest 5 activities as notifications
    api.getActivity(5).then(setNotifications).catch(() => {})
  }

  function handleSettingsOpen() {
    setSettingsOpen((o) => !o)
    setBellOpen(false)
    setOpen(false)
  }

  function formatTime(ts: string) {
    const d = new Date(ts)
    const diff = Math.floor((Date.now() - d.getTime()) / 1000)
    if (diff < 60) return "just now"
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
    return d.toLocaleDateString()
  }

  const initials = user?.full_name
    ? user.full_name
        .split(" ")
        .map((w) => w[0])
        .slice(0, 2)
        .join("")
        .toUpperCase()
    : "?";

  async function handleLogout() {
    try {
      await api.logout();
    } catch (err) {
      // ignore errors from server logout, still clear local state
      console.warn("Logout failed on server:", err);
    }
    try {
      localStorage.removeItem("token");
    } catch {}
    router.push("/login");
  }

  async function handleAddLead() {
    try {
      const name = window.prompt("Lead name:");
      if (!name) return;
      const email = window.prompt("Lead email:") || "";
      const company = window.prompt("Company:") || "";
      const intent = parseFloat(window.prompt("Intent score (0-100):") || "0");
      const deal = parseFloat(window.prompt("Deal value (number):") || "0");
      const status = (
        window.prompt("Status (hot, warm, cool):") || ""
      ).toLowerCase();

      const payload = {
        name,
        email,
        company,
        intent_score: Number.isFinite(intent) ? intent : 0,
        deal_value: Number.isFinite(deal) ? deal : 0,
        status: status || undefined,
      };

      await api.createLead(payload);
      // refresh UI
      router.refresh();
      // optionally close any open menus
      setOpen(false);
    } catch (err) {
      console.error("Add lead failed", err);
      alert("Failed to add lead");
    }
  }

  return (
    <header className="flex h-14 items-center justify-between border-b border-border bg-card px-4">
      {/* Logo and title */}
      <div className="flex items-center gap-3">
        <div className="flex size-9 items-center justify-center rounded-lg bg-primary/10 border border-primary/20">
          <Cpu className="size-5 text-primary" />
        </div>
        <div className="hidden sm:block">
          <h1 className="text-sm font-semibold text-foreground">
            Agentic Command Center
          </h1>
          <p className="text-xs text-muted-foreground">
            AI-powered sales intelligence
          </p>
        </div>
      </div>

      {/* Center stats */}
      <div className="hidden md:flex items-center gap-6">
        <div className="flex items-center gap-2">
          <div className="size-2 rounded-full bg-score-hot animate-pulse" />
          <span className="text-xs text-muted-foreground">
            <span className="font-mono text-foreground">
              {stats ? stats.hot_leads : "—"}
            </span>{" "}
            hot leads
          </span>
        </div>
        <div className="h-4 w-px bg-border" />
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">
            AI processed{" "}
            <span className="font-mono text-foreground">
              {stats ? stats.ai_actions_today : "—"}
            </span>{" "}
            actions today
          </span>
        </div>
        <div className="h-4 w-px bg-border" />
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">
            Pipeline:{" "}
            <span className="font-mono text-primary font-semibold">
              {stats ? stats.pipeline_value : "—"}
            </span>
          </span>
        </div>
      </div>

      {/* Right actions */}
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          className="hidden sm:flex gap-1.5"
          onClick={() => setModalOpen(true)}
        >
          <Plus className="size-3.5" />
          Add Lead
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="hidden sm:flex gap-1.5 text-muted-foreground"
          onClick={() => setImportOpen(true)}
        >
          <Upload className="size-3.5" />
          Import CSV
        </Button>
        <AddLeadModal
          open={modalOpen}
          onClose={() => setModalOpen(false)}
          onSuccess={() => onLeadCreated?.()}
        />
        <ImportCsvModal
          open={importOpen}
          onClose={() => setImportOpen(false)}
          onSuccess={() => onLeadCreated?.()}
        />
        {/* Bell */}
        <div className="relative">
          <Button variant="ghost" size="icon-sm" className="relative" onClick={handleBellOpen}>
            <Bell className="size-4" />
            {notifications.length > 0 && (
              <span className="absolute -top-0.5 -right-0.5 flex size-4 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground">
                {notifications.length}
              </span>
            )}
          </Button>
          {bellOpen && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setBellOpen(false)} />
              <div className="absolute right-0 top-10 z-20 w-72 rounded-lg border border-border bg-card shadow-lg py-1">
                <div className="px-3 py-2 border-b border-border">
                  <p className="text-xs font-semibold text-foreground">Recent AI Activity</p>
                </div>
                {notifications.length === 0 ? (
                  <p className="px-3 py-4 text-xs text-muted-foreground text-center">No activity yet</p>
                ) : (
                  notifications.map((n) => (
                    <div key={n.id} className="px-3 py-2 hover:bg-accent transition-colors border-b border-border/50 last:border-0">
                      <p className="text-xs text-foreground line-clamp-2">{n.message}</p>
                      <p className="text-[10px] text-muted-foreground mt-0.5">{n.leadName} · {formatTime(n.timestamp)}</p>
                    </div>
                  ))
                )}
              </div>
            </>
          )}
        </div>

        {/* Settings */}
        <div className="relative">
          <Button variant="ghost" size="icon-sm" onClick={handleSettingsOpen}>
            <Settings className="size-4" />
          </Button>
          {settingsOpen && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setSettingsOpen(false)} />
              <div className="absolute right-0 top-10 z-20 w-48 rounded-lg border border-border bg-card shadow-lg py-1">
                <div className="px-3 py-2 border-b border-border">
                  <p className="text-xs font-semibold text-foreground">Settings</p>
                </div>
                <a
                  href="http://localhost:8000/docs"
                  target="_blank"
                  rel="noreferrer"
                  className="flex w-full items-center gap-2 px-3 py-2 text-sm text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
                >
                  <Info className="size-4" />
                  API Docs
                </a>
                <a
                  href="https://github.com/vladinsc/-CRM-Agentic-AI"
                  target="_blank"
                  rel="noreferrer"
                  className="flex w-full items-center gap-2 px-3 py-2 text-sm text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
                >
                  <Github className="size-4" />
                  GitHub
                </a>
                <div className="flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground border-t border-border/50">
                  <Keyboard className="size-4" />
                  <span className="text-xs">v0.1.0 — EPIC 5 complete</span>
                </div>
              </div>
            </>
          )}
        </div>
        <div className="ml-2 h-6 w-px bg-border hidden sm:block" />
        <div className="relative">
          <Button
            variant="ghost"
            size="sm"
            className="flex gap-2"
            onClick={() => setOpen((o) => !o)}
          >
            <div className="flex size-6 items-center justify-center rounded-full bg-primary/20 text-xs font-semibold text-primary">
              {initials}
            </div>
            <span className="hidden sm:block text-sm">
              {user?.full_name ?? "…"}
            </span>
            <ChevronDown className="size-3 text-muted-foreground" />
          </Button>

          {open && (
            <>
              <div
                className="fixed inset-0 z-10"
                onClick={() => setOpen(false)}
              />
              <div className="absolute right-0 top-10 z-20 w-44 rounded-lg border border-border bg-card shadow-lg py-1">
                {user && (
                  <>
                    <div className="px-3 py-2 border-b border-border">
                      <p className="text-xs font-medium text-foreground truncate">
                        {user.full_name}
                      </p>
                      <p className="text-xs text-muted-foreground truncate">
                        {user.email}
                      </p>
                    </div>
                  </>
                )}
                <button
                  onClick={handleLogout}
                  className="flex w-full items-center gap-2 px-3 py-2 text-sm text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
                >
                  <LogOut className="size-4" />
                  Sign out
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
