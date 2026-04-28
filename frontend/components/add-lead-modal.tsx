"use client"

import { useState } from "react"
import { toast } from "sonner"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { api } from "@/lib/api"

interface AddLeadModalProps {
  open: boolean
  onClose: () => void
  onSuccess: () => void
}

export function AddLeadModal({ open, onClose, onSuccess }: AddLeadModalProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [form, setForm] = useState({
    name: "",
    company: "",
    role: "",
    email: "",
    phone: "",
    deal_value: "",
    currency: "EUR",
    last_activity_description: "",
    status: "new",
  })

  function set(field: string, value: string) {
    setForm((f) => ({ ...f, [field]: value }))
    setError(null)
  }

  function reset() {
    setForm({
      name: "",
      company: "",
      role: "",
      email: "",
      phone: "",
      deal_value: "",
      currency: "EUR",
      last_activity_description: "",
      status: "new",
    })
    setError(null)
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      await api.createLead({
        name: form.name,
        company: form.company,
        role: form.role,
        email: form.email,
        phone: form.phone || null,
        deal_value: form.deal_value ? form.deal_value : null,
        currency: form.currency,
        last_activity_description: form.last_activity_description || null,
        status: form.status,
      })
      toast.success(`Lead "${form.name}" created`, {
        description: "AI research started in background",
      })
      reset()
      onSuccess()
      onClose()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to create lead"
      setError(msg)
      toast.error("Failed to create lead", { description: msg })
    } finally {
      setLoading(false)
    }
  }

  function handleClose() {
    reset()
    onClose()
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && handleClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add New Lead</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            {/* Name */}
            <div className="col-span-2 space-y-1.5">
              <Label htmlFor="name">Full Name *</Label>
              <Input
                id="name"
                placeholder="Maria Ionescu"
                value={form.name}
                onChange={(e) => set("name", e.target.value)}
                required
              />
            </div>

            {/* Company */}
            <div className="space-y-1.5">
              <Label htmlFor="company">Company *</Label>
              <Input
                id="company"
                placeholder="Acme Corp"
                value={form.company}
                onChange={(e) => set("company", e.target.value)}
                required
              />
            </div>

            {/* Role */}
            <div className="space-y-1.5">
              <Label htmlFor="role">Role *</Label>
              <Input
                id="role"
                placeholder="CTO"
                value={form.role}
                onChange={(e) => set("role", e.target.value)}
                required
              />
            </div>

            {/* Email */}
            <div className="col-span-2 space-y-1.5">
              <Label htmlFor="email">Email *</Label>
              <Input
                id="email"
                type="email"
                placeholder="maria@acme.ro"
                value={form.email}
                onChange={(e) => set("email", e.target.value)}
                required
              />
            </div>

            {/* Phone */}
            <div className="space-y-1.5">
              <Label htmlFor="phone">Phone</Label>
              <Input
                id="phone"
                placeholder="+40 721 000 000"
                value={form.phone}
                onChange={(e) => set("phone", e.target.value)}
              />
            </div>

            {/* Deal Value */}
            <div className="space-y-1.5">
              <Label htmlFor="deal_value">Deal Value</Label>
              <Input
                id="deal_value"
                type="number"
                placeholder="45000"
                value={form.deal_value}
                onChange={(e) => set("deal_value", e.target.value)}
              />
            </div>

            {/* Currency */}
            <div className="space-y-1.5">
              <Label>Currency</Label>
              <Select value={form.currency} onValueChange={(v) => set("currency", v)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="EUR">EUR €</SelectItem>
                  <SelectItem value="USD">USD $</SelectItem>
                  <SelectItem value="GBP">GBP £</SelectItem>
                  <SelectItem value="RON">RON</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Status */}
            <div className="space-y-1.5">
              <Label>Status</Label>
              <Select value={form.status} onValueChange={(v) => set("status", v)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="new">New</SelectItem>
                  <SelectItem value="contacted">Contacted</SelectItem>
                  <SelectItem value="qualified">Qualified</SelectItem>
                  <SelectItem value="closed">Closed</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Last Activity */}
            <div className="col-span-2 space-y-1.5">
              <Label htmlFor="last_activity">Last Activity</Label>
              <Input
                id="last_activity"
                placeholder="Viewed pricing page 3x this week"
                value={form.last_activity_description}
                onChange={(e) => set("last_activity_description", e.target.value)}
              />
            </div>
          </div>

          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={handleClose} disabled={loading}>
              Cancel
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? "Creating…" : "Add Lead"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
